import os
import logging
import collections
from datetime import datetime
import StringIO
from gedcom import Gedcom, GedcomParseError
import boto
from bson.code import Code

from .tasks import update_row, update_tree
from bhs_api.persons import is_living_person, LIVING_PERSON_WHITELISTED_KEYS

THIS_YEAR = datetime.now().year
# google storage: OUTPUT_BUCKET = 'bhs-familytrees-json'
OUTPUT_BUCKET = '/data/bhs-familytrees-json'


def add_children(elem, prefix, props):
    for i in elem.children:
        if prefix:
            key = '_'.join((prefix, i.tag))
        else:
            key = i.tag
        if i.value:
            props[key] = i.value
        add_children(i, key, props)


class Gedcom2Persons:

    def __init__(self, gedcom, tree_num, file_id, onsave, dryrun=False):
        ''' main import function, receieve a parsed gedcom '''

        self.gedcom = gedcom
        self.tree_num = tree_num
        self.file_id = file_id
        self.onsave = onsave
        self.dryrun=dryrun

        form = ''
        ver = '?'
        date = 'Unknown'
        source = 'Unknown'
        head = self.gedcom.as_list[0]
        for i in head.children:
            tag = i.tag
            if tag == 'SOUR':
                source = i.value
            elif tag == 'DATE':
                date = i.value
                for j in i.children:
                    if j.tag == 'TIME':
                        date += " "+j.value
            elif tag == "SOUR":
                source = i.value
            elif tag == "GEDC":
                for j in i.children:
                    if j.tag == 'VERS':
                        ver = j.value
                    elif j.tag == 'FORM':
                        form = j.value

        # TODO: get more data - i.e. update date, author, etc.
        # TODO: tree number!!!
        root = {}
        add_children(head, None, root)
        count = 0
        for e in self.gedcom.as_dict.values():
            if e.is_individual:
                count += 1
        self.meta = dict (
                    date=date,
                    source=source,
                    gedc_ver=ver,
                    gedc_form=form,
                    num=tree_num,
                    persons = count,
                    file_id = file_id,
                    )
        update_tree.delay(self.meta)
        self.add_nodes()

    def save(self, data, name):
        ''' google storage code
        uri = boto.storage_uri(self.dest_bucket_name+name+'.json', 'gs')
        uri.new_key().set_contents_from_string(json.dumps(data))
        '''
        data['id'] = name
        data['tree_num'] = self.meta['num']
        data['tree_size'] = self.meta['persons']
        data['tree_file_id'] = self.meta['file_id']
        self.onsave(data, 'persons')

    def flatten(self, node_or_nodes, full=False):
        ret = []
        nodes = node_or_nodes if isinstance(node_or_nodes, collections.Iterable) else [node_or_nodes]
        for e in nodes:
            node_id = e.pointer[1:-1]
            node = dict(id=node_id, sex=e.gender)
            node['deceased'] = not is_living_person(e.deceased, e.birth_year)
            if not e.private:
                node['name'] = e.name
                if full and node['deceased']:
                    node['birth_year'] = e.birth_year
                    node['death_year'] = e.death_year
                    node['marriage_years'] = self.gedcom.marriage_years(e)
                    add_children(e, None, node)
            if not node['deceased']:
                # it's alive! delete all keys not in the living person whitelist
                for key in node:
                    if key not in LIVING_PERSON_WHITELISTED_KEYS:
                        del node[key]
            ret.append(node)
        return ret if isinstance(node_or_nodes, collections.Iterable) else ret[0]

    def find_partners(self, node, depth=0, exclude_ids=None):
        ret = []
        if not node.is_individual:
            return ret

        if exclude_ids:
            eids = exclude_ids + [node.pointer]
        else:
            eids = [node.pointer]

        for f in self.gedcom.families(node, "FAMS"):
            partner = None
            kids = []
            for i in f.children:
                if i.value in eids:
                    continue
                if i.tag in ("HUSB", "WIFE"):
                    try:
                        partner = self.flatten(self.gedcom.as_dict[i.value])
                    except KeyError:
                        logging.error("missing partner {} in tree {}".
                                      format(i.value, self.tree_num))
                elif i.tag == "CHIL":
                    try:
                        kids.append(self.gedcom.as_dict[i.value])
                    except KeyError:
                        logging.error("missing kid {} in tree {}".
                                      format(i.value, self.tree_num))
            if not partner:
                partner = {'name': [u"\u263A"]}
            partner["children"] = []
            if depth > 0:
                for e in kids:
                    kid = self.flatten(e)
                    if depth > 1:
                        kid["partners"] = self.find_partners(e, depth - 1,
                                                            eids)
                    partner["children"].append(kid)
            ret.append(partner)
        return ret


    def find_siblings(self, ptr, e):
        found = []
        siblings_ids = []
        for family in self.gedcom.families(e, "FAMC"):
            for sibling in \
                    self.gedcom.get_family_members(family, "CHIL"):
                siblings_ids.append(sibling.pointer)
                if sibling.pointer != ptr:
                    found.append(self.flatten(sibling))
        return found, siblings_ids

    def find_parents(self, e, siblings_ids):
        ''' gather the parents and their parents '''
        found = []
        parents = self.gedcom.get_parents(e)
        for i in parents:
            if not i.is_individual:
                continue
            parent = self.flatten(i)
            grandparents = self.gedcom.get_parents(i)
            parent["parents"] = self.flatten(grandparents)
            parent["partners"] = self.find_partners(i, depth=1,
                                            exclude_ids=siblings_ids)
            found.append(parent)
        return found

    def add_nodes(self):
        '''Add the self.gedcom nodes to the graph, extracting children data'''
        for ptr, e in self.gedcom.as_dict.items():
            node = self.flatten(e, full=True)
            if e.is_individual:
                node["partners"] = self.find_partners(e, depth=2)
                node["siblings"], siblings_ids = self.find_siblings(ptr, e)
                node["parents"] = self.find_parents(e, siblings_ids)
                self.save(node, node["id"])

def sync_ftrees(db, bucket=None, files=None):
    if bucket:
        uri = boto.storage_uri(bucket, 'gs')
        gedcoms = uri.get_bucket()
    else:
        gedcoms = files

    # prepare the tree_num hash
    tree_nums  = {}
    for i in db.genTreeIndividuals.map_reduce(
        Code("function() { emit (this.GenTreePath.split('/')[2].slice(0,-4), this.GTN) }"),
        Code("function(k, vs) {return vs[0]}"),
        "treeNums").find({}):
        try:
            tree_nums[i["_id"]] = int(i["value"].values()[0])
        except:
            tree_nums[i["_id"]] = i["value"]

    for i in gedcoms:
        filename = i if isinstance(i, str) else i.name
        tree_id = os.path.splitext(os.path.basename(filename))[0]
        try:
            tree_num = tree_nums[tree_id]
        except KeyError:
            logging.error("sorry, couldn't find the number of tree {}"
                          .format(filename))
            continue
            # num = int(raw_input("please enter the tree number you'd like yo use, or presss enter to exit"))

        dest_bucket_name = '/'.join((OUTPUT_BUCKET,str(tree_num),''))
        if os.path.exists(dest_bucket_name):
            logging.info("skipping tree {} as it already exists"
                         .format(tree_num))
            continue
        os.mkdir(dest_bucket_name)
        ''' google storage code follows
        uri = boto.storage_uri(dest_bucket_name+'root.json', 'gs')
        try:
            uri.get_key()
            # the tree exsist, move to the next
            continue
        except boto.exception.InvalidUriError:
            pass
        '''

        if isinstance(i, str):
            fd = open(i, 'r')
        else:
            # the boto way of doing things
            fd = StringIO.StringIO()
            i.get_file(fd)
            fd.seek(0)

        logging.info("parsing file {} number {}".format(filename, tree_num))
        try:
            g = Gedcom(fd=fd)
        except (SyntaxError, GedcomParseError) as e:
            logging.error("failed to parse gedcom: "+str(e))
            continue

        Gedcom2Jsons(g, tree_num, dest_bucket_name)
