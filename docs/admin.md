# System Administrator Guide

## General

Most administrative functions are ran through shell at the development and
production servers.  The scripts themselves are all
[here](https://github.com/Beit-Hatfutsot/dbs-back/tree/dev/scripts) and all
support the `-h` option for help. To activate a script you need to ssh into the
server, change to `bhs` user and from its home:

    $ cd api
    $ . env/bin/activate
    $ export PYTHONPATH=.
    
## Common Scenarios

### Load a tree

Haim wants to load a new tree to the system or update an existing tree with a
new version. Haim should provide the tree number.

Log in to bhs@bhs-infra (need to be wired to the Museum network) and look for
the tree's gedcom file.
Gedcom files are in `/media/bhpstorage/FamilyTree` and end in `.ged`.
The next part of the path is the thousands digits, i.e. 6 for tree id 6345 
and 12 for 12478.
When you know the full path type:

    $ cd api
    $ . env/bin/activate
    $ export PYTHONPATH=.
    $ scripts/migrate.py -c genTrees -g <gedcom_file_path> -i <tree_number> -s 0

The tree should be immediately available at
`http://dbs.bh.org.il/person?more=1&tree_number=<tree_number>`

### Image thumbnails are missing

This could be the result of the thumbnail file missing or having wrong access
control. If the thumbnail file exists but is not public, accessing the file
will result in an HTTP error 401, if the file does not exist the error code
will be 404. Use the bowser debugger to check the result code and in case it's
401, you need turn public access on using either [compute storage web
interface](https://console.cloud.google.com/storage/browser?project=bh-org-01)
or through google's gsutil:

    $ gsutil -m acl set -a public-read gs://bhs-thumbnails/<file_name>

### A partner wants a db dump

The dump script supports dumping to a zipped tar file as well as uploading to
an FTP server. When the partner has an FTP server you should pass in the values
using `--ftp-server`, `--ftp-user`, `--ftp-password` and optionally,
`--ftp-dir`. In case the partner does not have an FTP server, the script can
dump into an output directory, specified using the `-o` parameter or in `/tmp`
if omitted. 

    $ scripts/dump_mongo_to_csv.py ...


### Search results are not clickable or have have duplicates

Probably something is wrong with our search index. You'll need to rebuild the
index:

    $ scripts/dump_mongo_to_es.py -r

### Photos are missing
