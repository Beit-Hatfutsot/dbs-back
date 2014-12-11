#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import subprocess
import re
from itertools import groupby

import pymongo

import unicodedata


def is_hebrew(string):
    'A hacky way to check if our string is in Hebrew - check the 1rst char'
    # Make sure the string is UTF-8
    if type(string) != unicode:
        string = string.decode('utf-8')
    HEBREW_AB = unicode(u'אבגדהוזחטיכךלמםנןסעפףצץקרשת')
    if string[0] in HEBREW_AB:
        return True
    else:
        return False

def get_hebrew_dms(string):
    'Run Javascript code extracted from http://www.stevemorse.org/hebrew/dmheb.html'
    script = 'gen_hebrew_dm_soundex.js'
    try:
        output = subprocess.check_output([script, string])
    except(subprocess.CalledProcessError) as e:
        print e
        return None
    return output.strip()

def get_english_dms(string):
    'Using code from https://github.com/chrislit/abydos/blob/master/abydos/phonetic.py'
    result_set = dm_soundex(string)
    result = str(' '.join(list(result_set))) # Cast the value to format returned by get_hebrew_dms()
    return result

def get_bhp_soundex(string):
    '''Generate a dms from a string, then convert it to a format stored in BHP database.
    get_bhp_soundex('ירושלים') ==> '194860 197486'  ==> 'ZZ H194860 H197486 ZZ ' # Yes, trailing space!
    get_bhp_soundex('jerusalem') ==> '494860 194860' ==> 'ZZ E494860 E194860 ZZ '
    '''
    if is_hebrew(string):
        dms = get_hebrew_dms(string)
        to_list = dms.split(' ')
        lang_list = ['H' + s for s in to_list]
    else:
        dms = get_english_dms(string)
        to_list = dms.split(' ')
        lang_list = ['E' + s for s in to_list]

    lang_string = ' '.join(lang_list)
    return 'ZZ ' + lang_string + ' ZZ '


def get_dms(string):
    '''Generate a dms from a string'''
    if is_hebrew(string):
        dms = get_hebrew_dms(string)
    else:
        dms = get_english_dms(string)
    return dms

def switch_bhp_soundex(soundex):
    if 'E' in soundex:
        return soundex.replace('E', 'H')
    elif 'H' in soundex:
        return soundex.replace('H', 'E')
    else:
        print 'Unexpected soundex value', soundex
        return None

def update_dm(collection_obj):
    for name_doc in collection_obj.find():
        oid = name_doc['_id']
        index_for = name_doc['lowercase']
        dm = get_dmetaphone(index_for)
        name_doc['double_metaphone'] = dm
        collection_obj.find_and_modify(query={'_id': oid}, update=name_doc)
        #print name_doc

def get_similar_strings(string, collection_obj):
    'Searches in the UnitHeaderDMSoundex field of bhp6 comaptible db'
    dms = get_dms(string)
    found = []
    for dms_value in dms.split(' '):
        regex = re.compile(dms_value)
        cursor = collection_obj.find({"UnitHeaderDMSoundex": regex})
        for doc in cursor:
            found.append(doc)

    return found

def dm_soundex(word, maxlength=6, reverse=False, zero_pad=True):
    """Return the Daitch-Mokotoff Soundex values of a word as a set
        A collection is necessary since there can be multiple values for a
        single word.

    Arguments:
    word -- the word to translate to D-M Soundex
    maxlength -- the length of the code returned (defaults to 6)
    reverse -- reverse the word before computing the selected Soundex (defaults
        to False); This results in "Reverse Soundex"
    zero_pad -- pad the end of the return value with 0s to achieve a maxlength
        string
    """
    _dms_table = {'STCH': (2, 4, 4), 'DRZ': (4, 4, 4), 'ZH': (4, 4, 4),
                  'ZHDZH': (2, 4, 4), 'DZH': (4, 4, 4), 'DRS': (4, 4, 4),
                  'DZS': (4, 4, 4), 'SCHTCH': (2, 4, 4), 'SHTSH': (2, 4, 4),
                  'SZCZ': (2, 4, 4), 'TZS': (4, 4, 4), 'SZCS': (2, 4, 4),
                  'STSH': (2, 4, 4), 'SHCH': (2, 4, 4), 'D': (3, 3, 3),
                  'H': (5, 5, '_'), 'TTSCH': (4, 4, 4), 'THS': (4, 4, 4),
                  'L': (8, 8, 8), 'P': (7, 7, 7), 'CHS': (5, 54, 54),
                  'T': (3, 3, 3), 'X': (5, 54, 54), 'OJ': (0, 1, '_'),
                  'OI': (0, 1, '_'), 'SCHTSH': (2, 4, 4), 'OY': (0, 1, '_'),
                  'Y': (1, '_', '_'), 'TSH': (4, 4, 4), 'ZDZ': (2, 4, 4),
                  'TSZ': (4, 4, 4), 'SHT': (2, 43, 43), 'SCHTSCH': (2, 4, 4),
                  'TTSZ': (4, 4, 4), 'TTZ': (4, 4, 4), 'SCH': (4, 4, 4),
                  'TTS': (4, 4, 4), 'SZD': (2, 43, 43), 'AI': (0, 1, '_'),
                  'PF': (7, 7, 7), 'TCH': (4, 4, 4), 'PH': (7, 7, 7),
                  'TTCH': (4, 4, 4), 'SZT': (2, 43, 43), 'ZDZH': (2, 4, 4),
                  'EI': (0, 1, '_'), 'G': (5, 5, 5), 'EJ': (0, 1, '_'),
                  'ZD': (2, 43, 43), 'IU': (1, '_', '_'), 'K': (5, 5, 5),
                  'O': (0, '_', '_'), 'SHTCH': (2, 4, 4), 'S': (4, 4, 4),
                  'TRZ': (4, 4, 4), 'SHD': (2, 43, 43), 'DSH': (4, 4, 4),
                  'CSZ': (4, 4, 4), 'EU': (1, 1, '_'), 'TRS': (4, 4, 4),
                  'ZS': (4, 4, 4), 'STRZ': (2, 4, 4), 'UY': (0, 1, '_'),
                  'STRS': (2, 4, 4), 'CZS': (4, 4, 4),
                  'MN': ('6_6', '6_6', '6_6'), 'UI': (0, 1, '_'),
                  'UJ': (0, 1, '_'), 'UE': (0, '_', '_'), 'EY': (0, 1, '_'),
                  'W': (7, 7, 7), 'IA': (1, '_', '_'), 'FB': (7, 7, 7),
                  'STSCH': (2, 4, 4), 'SCHT': (2, 43, 43),
                  'NM': ('6_6', '6_6', '6_6'), 'SCHD': (2, 43, 43),
                  'B': (7, 7, 7), 'DSZ': (4, 4, 4), 'F': (7, 7, 7),
                  'N': (6, 6, 6), 'CZ': (4, 4, 4), 'R': (9, 9, 9),
                  'U': (0, '_', '_'), 'V': (7, 7, 7), 'CS': (4, 4, 4),
                  'Z': (4, 4, 4), 'SZ': (4, 4, 4), 'TSCH': (4, 4, 4),
                  'KH': (5, 5, 5), 'ST': (2, 43, 43), 'KS': (5, 54, 54),
                  'SH': (4, 4, 4), 'SC': (2, 4, 4), 'SD': (2, 43, 43),
                  'DZ': (4, 4, 4), 'ZHD': (2, 43, 43), 'DT': (3, 3, 3),
                  'ZSH': (4, 4, 4), 'DS': (4, 4, 4), 'TZ': (4, 4, 4),
                  'TS': (4, 4, 4), 'TH': (3, 3, 3), 'TC': (4, 4, 4),
                  'A': (0, '_', '_'), 'E': (0, '_', '_'), 'I': (0, '_', '_'),
                  'AJ': (0, 1, '_'), 'M': (6, 6, 6), 'Q': (5, 5, 5),
                  'AU': (0, 7, '_'), 'IO': (1, '_', '_'), 'AY': (0, 1, '_'),
                  'IE': (1, '_', '_'), 'ZSCH': (4, 4, 4),
                  'CH':((5, 4), (5, 4), (5, 4)),
                  'CK':((5, 45), (5, 45), (5, 45)),
                  'C':((5, 4), (5, 4), (5, 4)),
                  'J':((1, 4), ('_', 4), ('_', 4)),
                  'RZ':((94, 4), (94, 4), (94, 4)),
                  'RS':((94, 4), (94, 4), (94, 4))}

    _dms_order = {'A':('AI', 'AJ', 'AU', 'AY', 'A'), 'B':('B'),
                  'C':('CHS', 'CSZ', 'CZS', 'CH', 'CK', 'CS', 'CZ', 'C'),
                  'D':('DRS', 'DRZ', 'DSH', 'DSZ', 'DZH', 'DZS', 'DS', 'DT',
                       'DZ', 'D'), 'E':('EI', 'EJ', 'EU', 'EY', 'E'),
                  'F':('FB', 'F'), 'G':('G'), 'H':('H'),
                  'I':('IA', 'IE', 'IO', 'IU', 'I'), 'J':('J'),
                  'K':('KH', 'KS', 'K'), 'L':('L'), 'M':('MN', 'M'),
                  'N':('NM', 'N'), 'O':('OI', 'OJ', 'OY', 'O'),
                  'P':('PF', 'PH', 'P'), 'Q':('Q'), 'R':('RS', 'RZ', 'R'),
                  'S':('SCHTSCH', 'SCHTCH', 'SCHTSH', 'SHTCH', 'SHTSH', 'STSCH',
                       'SCHD', 'SCHT', 'SHCH', 'STCH', 'STRS', 'STRZ', 'STSH',
                       'SZCS', 'SZCZ', 'SCH', 'SHD', 'SHT', 'SZD', 'SZT', 'SC',
                       'SD', 'SH', 'ST', 'SZ', 'S'),
                  'T':('TTSCH', 'TSCH', 'TTCH', 'TTSZ', 'TCH', 'THS', 'TRS',
                       'TRZ', 'TSH', 'TSZ', 'TTS', 'TTZ', 'TZS', 'TC', 'TH',
                       'TS', 'TZ', 'T'), 'U':('UE', 'UI', 'UJ', 'UY', 'U'),
                  'V':('V'), 'W':('W'), 'X':('X'), 'Y':('Y'),
                  'Z':('ZHDZH', 'ZDZH', 'ZSCH', 'ZDZ', 'ZHD', 'ZSH', 'ZD', 'ZH',
                       'ZS', 'Z')}

    _vowels = tuple('AEIJOUY')
    dms = [''] # initialize empty code list

    # Require a maxlength of at least 6 and not more than 64
    if maxlength is not None:
        maxlength = min(max(6, maxlength), 64)
    else:
        maxlength = 64

    # uppercase, normalize, decompose, and filter non-A-Z
    word = unicodedata.normalize('NFKD', unicode(word.upper()))
    word = word.replace(u'ß', 'SS')
    word = ''.join([c for c in word if c in
                    tuple('ABCDEFGHIJKLMNOPQRSTUVWXYZ')])

    # Nothing to convert, return base case
    if not word:
        if zero_pad:
            return set(['0'*maxlength])
        else:
            return set(['0'])

    # Reverse word if computing Reverse Soundex
    if reverse:
        word = word[::-1]

    pos = 0
    while pos < len(word):
        # Iterate through _dms_order, which specifies the possible substrings
        # for which codes exist in the Daitch-Mokotoff coding
        for sstr in _dms_order[word[pos]]:
            if word[pos:].startswith(sstr):
                # Having determined a valid substring start, retrieve the code
                dm_val = _dms_table[sstr]

                # Having retried the code (triple), determine the correct
                # positional variant (first, pre-vocalic, elsewhere)
                if pos == 0:
                    dm_val = dm_val[0]
                elif (pos+len(sstr) < len(word) and
                      word[pos+len(sstr)] in _vowels):
                    dm_val = dm_val[1]
                else:
                    dm_val = dm_val[2]

                # Build the code strings
                if isinstance(dm_val, tuple):
                    dms = [_ + unicode(dm_val[0]) for _ in dms] \
                            + [_ + unicode(dm_val[1]) for _ in dms]
                else:
                    dms = [_ + unicode(dm_val) for _ in dms]
                pos += len(sstr)
                break

    # Filter out double letters and _ placeholders
    dms = [''.join([c for c in _delete_consecutive_repeats(_) if c != '_'])
           for _ in dms]

    # Trim codes and return set
    if zero_pad:
        dms = [(_ + ('0'*maxlength))[:maxlength] for _ in dms]
    else:
        dms = [_[:maxlength] for _ in dms]
    return set(dms)

def _delete_consecutive_repeats(word):
    """Return word with all contiguous repeating characters collapsed to
    a single instance
    """
    return ''.join(char for char, _ in groupby(word))

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('search')
    parser.add_argument('-c', '--collection', default='familyNames')
    parser.add_argument('-b', '--database', default='bhp6')

    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()
    db = pymongo.Connection()[args.database]
    collection = db[args.collection]
    retval = get_similar_strings(args.search, collection)
    if not retval:
        print 'Nothing found for {}'.format(args.search)
    else:
        for doc in retval:
            print doc['Header']

    
