import json
import re
from collections import defaultdict
from .keywords import INST_ABBR, AMBIGUOUS, ABBR, MANUAL_ADDED, COUNTRY_REG
from string import punctuation
from unidecode import unidecode
from pathlib import Path
from .utils import download_grid_data


path = Path("./grid_matcher")
grid_path = path / "grid"
if not grid_path.exists():
    download_grid_data()  # if GRID data does not exist, download it locally


def remove_punctuations(affiliation):
    """
    replace the punctuations in text with spaces
    :param affiliation: the raw affiliation name
    :return: processed text
    """
    affiliation = unidecode(affiliation).lower()
    for _pun in punctuation + "-":
        if _pun == '&':
            affiliation = affiliation.replace(_pun, ' and ')
        if _pun == '\'':
            affiliation = affiliation.replace(_pun, '')
        else:
            affiliation = affiliation.replace(_pun, ' ')
    affiliation = re.sub(r'\s\s+', ' ', affiliation)  # remove redundant spaces
    return affiliation


def country_mapping(aff: str):
    for key, value in COUNTRY_REG.items():
        if re.findall(r'{}'.format(key), aff):
            return value
    return ""


def pre_processing_name(affiliation):
    """
    replace possible abbreviations in affiliation names like Uni., Tech., Inst., and etc.
    :param affiliation: affiliation name
    :return:
    """
    for key, value in ABBR.items():
        affiliation = re.sub(key, value, affiliation)
    affiliation = remove_punctuations(affiliation)
    for key, value in INST_ABBR.items():
        affiliation = affiliation.replace(key, value)
    return affiliation


def ambiguous_or_not(name: str):
    # ignore ambiguous grid names in reg pattern
    if len(name) >= 3 and name not in AMBIGUOUS and not re.findall(
            r"^institute of.{3,20}$|^department of.{3,20}$|^college of.{3,20}$|^ministry of .{3,20}$", name):
        return True
    else:
        return False


def get_parent(name, parent_dic: dict):
    if name != parent_dic[name]:
        return get_parent(parent_dic[name], parent_dic)
    else:
        return name


def grid_matcher_build():
    """
    This function is to process standard organization names, aliases and labels from GRID
    :return: No return, will save the generated tuples in json format
    """
    grid_read = json.load(open('./grid_matcher/grid/grid.json', 'r', encoding='UTF-8'))

    # name_match is used to map regular expression to its official name, the length and the (list of) valid grid id(s)
    country_string_match = defaultdict(lambda: defaultdict(lambda: ""))
    country_name_grid_id = defaultdict(lambda: [])
    gid_country = {}
    parent = {}

    all_string_match = {}
    all_name_grid_id = defaultdict(lambda: [])

    for dic in grid_read['institutes']:
        if 'name' in dic.keys() and 'addresses' in dic.keys():
            parent_list = [x['id'] for x in dic['relationships'] if x['type'] == 'Parent']
            parent[dic['id']] = parent_list[0] if parent_list else dic['id']

            # exclude the bracketed contents
            std_name = re.sub(r'\s(?=\()[^}]*(\))', '', dic['name'])  # remove bracketed contents at the end
            country = dic['addresses'][0]['country']
            gid_country[dic['id']] = country
            country_name_grid_id[(std_name, country)].append(dic['id'])  # possible GRID IDs
            all_name_grid_id[std_name].append(dic['id'])
            unified_name = re.sub(r'^the\s', '', std_name, flags=re.I)  # remove 'the' at the beginning
            unified_name = remove_punctuations(unified_name)
            if ambiguous_or_not(unified_name):
                country_string_match[country][unified_name] = std_name
                all_string_match[unified_name] = std_name
            for alias in dic['aliases']:
                alias = remove_punctuations(alias)
                if ambiguous_or_not(alias):
                    country_string_match[country][alias] = std_name
                    all_string_match[alias] = std_name
            if 'labels' in dic.keys():
                for label in dic['labels']:
                    _label = remove_punctuations(label['label'])
                    if ambiguous_or_not(_label):
                        country_string_match[country][_label] = std_name
                        all_string_match[_label] = std_name
    for key, value in all_string_match.items():
        if len(all_name_grid_id[value]) > 1 and len(
                set([get_parent(y, parent) for y in all_name_grid_id[value]])) == 1:
            tmp = [parent[y] for y in all_name_grid_id[value]]
            all_name_grid_id[value] = [max(set(tmp), key=tmp.count)]

    for country, raw_aff, _name in MANUAL_ADDED:
        country_string_match[country][raw_aff] = _name
        all_string_match[raw_aff] = _name

    # Add customised abbreviations
    country_final_dic = {}

    for country in country_string_match.keys():
        sorted_dic = sorted(country_string_match[country].items(), key=lambda x: len(x[0]), reverse=True)
        normal = [(x[0], x[1], country_name_grid_id[(x[1], country)]) for x in sorted_dic if
                  len(x[0]) > 2 and re.findall(r'\s.*\s', x[0])]
        special = [(x[0], x[1], country_name_grid_id[(x[1], country)]) for x in sorted_dic if
                   len(x[0]) > 2 and not re.findall(r'\s.*\s', x[0])]
        country_final_dic[country] = (normal, special)

    all_sorted = sorted(all_string_match.items(), key=lambda x: len(x[0]), reverse=True)
    normal = [(x[0], x[1], all_name_grid_id[x[1]]) for x in all_sorted if
              len(x[0]) > 2 and re.findall(r'\s.*\s', x[0])]
    special = [(x[0], x[1], all_name_grid_id[x[1]]) for x in all_sorted if
               len(x[0]) > 2 and not re.findall(r'\s.*\s', x[0])]
    all_final_match = (normal, special)
    return country_final_dic, all_final_match, gid_country


class GridMatcher:
    """
    The primary grid_matcher to map affiliation names to GRID ids.
    """

    def __init__(self):
        print("Initializing Matcher...")
        self.country_final_dic, self.all_final_match, self.gid_country = grid_matcher_build()

    def match(self, raw_aff: str):
        raw_aff = raw_aff.replace("#TAB#", ' ')
        raw_aff = raw_aff.replace("#N#", ' ')
        country = country_mapping(raw_aff)
        affiliation = pre_processing_name(raw_aff)
        if country:
            for reg, std_name, grid_id in self.country_final_dic[country][0]:
                if reg in affiliation:
                    return std_name, grid_id, [country]
            for reg, std_name, grid_id in self.country_final_dic[country][1]:
                if affiliation == reg or \
                        (affiliation.startswith(reg + ' ')) \
                        or affiliation.endswith(' ' + reg) \
                        or (' ' + reg + ' ' in affiliation):
                    return std_name, grid_id, [country]
        else:
            for reg, std_name, grid_id in self.all_final_match[0]:
                if reg in affiliation:
                    return std_name, grid_id, [self.gid_country[gid] for gid in grid_id]
            for reg, std_name, grid_id in self.all_final_match[1]:
                if affiliation == reg or \
                        (affiliation.startswith(reg + ' ')) \
                        or affiliation.endswith(' ' + reg) \
                        or (' ' + reg + ' ' in affiliation):
                    return std_name, grid_id, [self.gid_country[gid] for gid in grid_id]
        return "", [], affiliation, [country]
