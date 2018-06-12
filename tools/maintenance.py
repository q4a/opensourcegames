"""
    Runs a series of maintenance operations on the collection of entry files, updating the table of content files for
    each category as well as creating a statistics file.

    Counts the number of records each sub-folder and updates the overview.
    Sorts the entries in the contents files of each sub folder alphabetically.

    This script runs with Python 3, it could also with Python 2 with some minor tweaks probably.
"""

import os
import re
import urllib.request
import http.client
import datetime
import json

TOC = '_toc.md'


def read_text(file):
    """
    Reads a whole text file (UTF-8 encoded).
    """
    with open(file, mode='r', encoding='utf-8') as f:
        text = f.read()
    return text


def read_first_line(file):
    """
    Convenience function because we only need the first line of a category overview really.
    """
    with open(file, mode='r', encoding='utf-8') as f:
        line = f.readline()
    return line


def write_text(file, text):
    """
    Writes a whole text file (UTF-8 encoded).
    """
    with open(file, mode='w', encoding='utf-8') as f:
        f.write(text)


def get_category_paths():
    """
    Returns all sub folders of the games path.
    """
    return [os.path.join(games_path, x) for x in os.listdir(games_path) if os.path.isdir(os.path.join(games_path, x))]


def get_entry_paths(category_path):
    """
    Returns all files of a category path, except for '_toc.md'.
    """
    return [os.path.join(category_path, x) for x in os.listdir(category_path) if x != TOC and os.path.isfile(os.path.join(category_path, x))]


def extract_overview_for_toc(file):
    """
    Parses a file for some interesting fields and concatenates the content.
    
    To be displayed after the game name in the category TOCs.
    """
    info = infos[file]

    output = []

    if 'code language' in info:
        output.extend(info['code language'])

    if 'code license' in info:
        output.extend(info['code license'])

    # state
    if 'state' in info:
        output.extend(info['state'])

    output = ", ".join(output)

    return output


def update_readme():
    """
    Recounts entries in sub categories and writes them to the readme.
    Also updates the _toc files in the categories directories.

    Note: The Readme must have a specific structure at the beginning, starting with "# Open Source Games" and ending
    on "A collection.."

    Needs to be performed regularly.
    """
    print('update readme file')

    # read readme
    readme_text = read_text(readme_file)

    # compile regex for identifying the building blocks
    regex = re.compile(r"(# Open Source Games\n\n)(.*)(\nA collection.*)", re.DOTALL)

    # apply regex
    matches = regex.findall(readme_text)
    assert len(matches) == 1
    matches = matches[0]
    start = matches[0]
    end = matches[2]

    # get sub folders
    category_paths = get_category_paths()

    # assemble paths
    toc_paths = [os.path.join(path, TOC) for path in category_paths]

    # get titles (discarding first two ("# ") and last ("\n") characters)
    category_titles = [read_first_line(path)[2:-1] for path in toc_paths]

    # get number of files (minus 1 for the already existing TOC file) in each sub folder
    n_entries = [len(os.listdir(path)) - 1 for path in category_paths]

    # combine titles, category names, numbers in one list
    info = zip(category_titles, [os.path.basename(path) for path in category_paths], n_entries)

    # sort according to sub category title (should be unique)
    info = sorted(info, key=lambda x:x[0])

    # assemble output
    update = ['- **[{}](games/{}/{})** ({})\n'.format(entry[0], entry[1], TOC, entry[2]) for entry in info]
    update = "{} entries\n".format(sum(n_entries)) + "".join(update)

    # insert new text in the middle
    text = start + "[comment]: # (start of autogenerated content, do not edit)\n" + update + "\n[comment]: # (end of autogenerated content)" + end

    # write to readme
    write_text(readme_file, text)


def update_category_tocs():
    """
    Lists all entries in all sub folders and generates the list in the toc file.

    Needs to be performed regularly.
    """
    # get category paths
    category_paths = get_category_paths()

    # for each category
    for category_path in category_paths:
        print('generate toc for {}'.format(os.path.basename(category_path)))

        # read toc header line
        toc_file = os.path.join(category_path, TOC)
        toc_header = read_first_line(toc_file) # stays as is

        # get paths of all entries in this category
        entry_paths = get_entry_paths(category_path)

        # get titles (discarding first two ("# ") and last ("\n") characters)
        titles = [read_first_line(path)[2:-1] for path in entry_paths]

        # get more interesting info
        more = [extract_overview_for_toc(path) for path in entry_paths]

        # combine name, file name and more info
        info = zip(titles, [os.path.basename(path) for path in entry_paths], more)

        # sort according to entry title (should be unique)
        info = sorted(info, key=lambda x:x[0])

        # assemble output
        update = ['- **[{}]({})** ({})\n'.format(*entry) for entry in info]
        update = "".join(update)

        # combine with toc header
        text = toc_header + '\n' + "[comment]: # (start of autogenerated content, do not edit)\n" + update + "\n[comment]: # (end of autogenerated content)"

        # write to toc file
        with open(toc_file, mode='w', encoding='utf-8') as f:
            f.write(text)


def check_validity_external_links():
    """
    Checks all external links it can find for validity. Prints those with non OK HTTP responses. Does only need to be run
    from time to time.
    """
    # regex for finding urls (can be in <> or in () or a whitespace
    regex = re.compile(r"[\s\n]<(http.+?)>|\]\((http.+?)\)|[\s\n](http[^\s\n]+)")

    # count
    number_checked_links = 0

    # get category paths
    category_paths = get_category_paths()

    # for each category
    for category_path in category_paths:
        print('check links for {}'.format(os.path.basename(category_path)))

        # get entry paths
        entry_paths = get_entry_paths(category_path)

        # for each entry
        for entry_path in entry_paths:
            # read entry
            with open(entry_path, 'r', 'utf-8') as f:
                content = f.read()

            # apply regex
            matches = regex.findall(content)

            # for each match
            for match in matches:

                # for each possible clause
                for url in match:

                    # if there was something
                    if url:
                        try:
                            # without a special headers, frequent 403 responses occur
                            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64)'})
                            urllib.request.urlopen(req)
                        except urllib.error.HTTPError as e:
                            print("{}: {} - {}".format(os.path.basename(entry_path), url, e.code))
                        except http.client.RemoteDisconnected:
                            print("{}: {} - disconnected without response".format(os.path.basename(entry_path), url))

                        number_checked_links += 1

                        if number_checked_links % 50 == 0:
                            print("{} links checked".format(number_checked_links))

    print("{} links checked".format(number_checked_links))


def check_template_leftovers():
    """
    Checks for template leftovers.

    Should be run only occasionally.
    """

    # load template and get all lines
    text = read_text(os.path.join(games_path, 'template.md'))
    text = text.split('\n')
    check_strings = [x for x in text if x and not x.startswith('##')]

    # get category paths
    category_paths = get_category_paths()

    # for each category
    for category_path in category_paths:
        # get paths of all entries in this category
        entry_paths = get_entry_paths(category_path)

        for entry_path in entry_paths:
            # read it line by line
            content = read_text(entry_path)

            for check_string in check_strings:
                if content.find(check_string) >= 0:
                    print('{}: found {}'.format(os.path.basename(entry_path), check_string))


def parse_entry(content):
    """
    Returns a dictionary of the features of the content
    """

    info = {}

    # read title
    regex = re.compile(r"^# (.*)")
    matches = regex.findall(content)
    assert len(matches) == 1
    info['title'] = matches[0]

    # first read all field names
    regex = re.compile(r"^- (.*?): ", re.MULTILINE)
    fields = regex.findall(content)

    # iterate over found field
    for field in fields:
        regex = re.compile(r"- {}: (.*)".format(field))
        matches = regex.findall(content)
        assert len(matches) == 1 # every field should only be present once
        v = matches[0]

        # first store as is
        info[field.lower()+'-raw'] = v

        # remove parenthesis
        v = re.sub(r'\([^)]*\)', '', v)

        # split on ','
        v = v.split(',')

        # strip
        v = [x.strip() for x in v]

        # remove all being false (empty)
        v = [x for x in v if x]

        # if entry is of structure <..> remove <>
        v = [x[1:-1] if x[0] is '<' and x[-1] is '>' else x for x in v]

        # store in info
        info[field.lower()] = v

    # checks

    # essential fields
    essential_fields = ['home', 'state', 'code repository']
    for field in essential_fields:
        if field not in info:
            print('Essential field "{}" missing in entry "{}"'.format(field, info['title']))
            return info # so that the rest can run through

    # state must contain either beta or mature but not both
    v = info['state']
    if 'beta' in v != 'mature' in v:
        print('State must be one of <"beta", "mature"> in entry "{}"'.format(info['title']))
        return info # so that the rest can run through

    # urls in home, download, play and code repositories must start with http or https (or git)
    for field in ['home', 'download', 'play', 'code repository']:
        if field in info:
            for url in info[field]:
                if not (url.startswith('http://') or url.startswith('https://') or url.startswith('git://')):
                    print('URL "{}" in entry "{}" does not start with http'.format(url, info['title']))

    # github repositories should not end on .git
    repos = info['code repository']
    for repo in repos:
        if repo.startswith('https://github.com/') and repo.endswith('.git'):
            print('Github repo {} in entry "{}" should not end on .git.'.format(repo, info['title']))

    # extract inactive
    phrase = 'inactive since '
    inactive_year = [x[len(phrase):] for x in info['state'] if x.startswith(phrase)]
    assert len(inactive_year) <= 1
    if inactive_year:
        info['inactive'] = inactive_year[0]

    return info


def assemble_infos():
    """
    Parses all entries and assembles interesting infos about them.
    """
    # get category paths
    category_paths = get_category_paths()

    # a database of all important infos about the entries
    infos = {}

    # for each category
    for category_path in category_paths:
        # get paths of all entries in this category
        entry_paths = get_entry_paths(category_path)

        # get titles (discarding first two ("# ") and last ("\n") characters)
        category = read_first_line(os.path.join(category_path, TOC))[2:-1]

        for entry_path in entry_paths:
            # read entry
            content = read_text(entry_path)

            # parse entry
            info = parse_entry(content)

            # add category
            info['category'] = category

            # add file information
            info['file'] = os.path.basename(entry_path)[:-3] # [:-3] to cut off the .md

            # add to list
            infos[entry_path] = info

    return infos


def generate_statistics():
    """
    Generates the statistics page.

    Should be done every time the entries change.
    """

    # for this function replace infos with infos.values
    infois = infos.values()

    # start the page
    statistics_path = os.path.join(games_path, 'statistics.md')
    statistics = '[comment]: # (autogenerated content, do not edit)\n# Statistics\n\n'

    # total number
    number_entries = len(infois)
    rel = lambda x: x / number_entries * 100 # conversion to percent
    statistics += 'analyzed {} entries on {}\n\n'.format(number_entries, datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    # State (beta, mature, inactive)
    statistics += '## State\n\n'

    number_state_beta = sum(1 for x in infois if 'beta' in x['state'])
    number_state_mature = sum(1 for x in infois if 'mature' in x['state'])
    number_inactive = sum(1 for x in infois if 'inactive' in x)
    statistics += '- mature: {} ({:.1f}%)\n- beta: {} ({:.1f}%)\n- inactive: {} ({:.1f}%)\n\n'.format(number_state_mature, rel(number_state_mature), number_state_beta, rel(number_state_beta), number_inactive, rel(number_inactive))

    if number_inactive > 0:
        entries_inactive = [(x['title'], x['inactive']) for x in infois if 'inactive' in x]
        entries_inactive.sort(key=lambda x: x[0])  # first sort by name
        entries_inactive.sort(key=lambda x: x[1], reverse=True) # then sort by inactive year (more recently first)
        entries_inactive = ['{} ({})'.format(*x) for x in entries_inactive]
        statistics += '##### Inactive State\n\n' + ', '.join(entries_inactive) + '\n\n'

    # Language
    statistics += '## Code Languages\n\n'
    field = 'code language'

    # those without language tag
    number_no_language = sum(1 for x in infois if field not in x)
    if number_no_language > 0:
        statistics += 'Without language tag: {} ({:.1f}%)\n\n'.format(number_no_language, rel(number_no_language))
        entries_no_language = [x['title'] for x in infois if field not in x]
        entries_no_language.sort()
        statistics += ', '.join(entries_no_language) + '\n\n'

    # get all languages together
    languages = []
    for info in infois:
        if field in info:
            languages.extend(info[field])

    unique_languages = set(languages)
    unique_languages = [(l, languages.count(l) / len(languages)) for l in unique_languages]
    unique_languages.sort(key=lambda x: x[0]) # first sort by name
    unique_languages.sort(key=lambda x: x[1], reverse=True) # then sort by occurrence (highest occurrence first)
    unique_languages = ['- {} ({:.1f}%)\n'.format(x[0], x[1]*100) for x in unique_languages]
    statistics += '##### Language frequency\n\n' + ''.join(unique_languages) + '\n'

    # Licenses
    statistics += '## Code licenses\n\n'
    field = 'code license'

    # those without license
    number_no_license = sum(1 for x in infois if field not in x)
    if number_no_license > 0:
        statistics += 'Without license tag: {} ({:.1f}%)\n\n'.format(number_no_license, rel(number_no_license))
        entries_no_license = [x['title'] for x in infois if field not in x]
        entries_no_license.sort()
        statistics += ', '.join(entries_no_license) + '\n\n'

    # get all licenses together
    licenses = []
    for info in infois:
        if field in info:
            licenses.extend(info[field])

    unique_licenses = set(licenses)
    unique_licenses = [(l, licenses.count(l) / len(licenses)) for l in unique_licenses]
    unique_licenses.sort(key=lambda x: x[0]) # first sort by name
    unique_licenses.sort(key=lambda x: -x[1]) # then sort by occurrence (highest occurrence first)
    unique_licenses = ['- {} ({:.1f}%)\n'.format(x[0], x[1]*100) for x in unique_licenses]
    statistics += '##### Licenses frequency\n\n' + ''.join(unique_licenses) + '\n'

    # Keywords
    statistics += '## Keywords\n\n'
    field = 'keywords'

    # get all keywords together
    keywords = []
    for info in infois:
        if field in info:
            keywords.extend(info[field])

    unique_keywords = set(keywords)
    unique_keywords = [(l, keywords.count(l) / len(keywords)) for l in unique_keywords]
    unique_keywords.sort(key=lambda x: x[0]) # first sort by name
    unique_keywords.sort(key=lambda x: -x[1]) # then sort by occurrence (highest occurrence first)
    unique_keywords = ['- {} ({:.1f}%)\n'.format(x[0], x[1]*100) for x in unique_keywords]
    statistics += '##### Keywords frequency\n\n' + ''.join(unique_keywords) + '\n'

    with open(statistics_path, mode='w', encoding='utf-8') as f:
        f.write(statistics)


def export_json():
    """
    Parses all entries, collects interesting info and stores it in a json file suitable for displaying
    with a dynamic table in a browser.
    """

    # make database out of it
    db = {}
    db['headings'] = ['Game', 'Description', 'Download', 'State', 'Keywords', 'Source']

    entries = []
    for info in infos.values():

        entry = []

        # game
        entry.append('{} (<a href="{}">home</a>, <a href="{}">entry</a>)'.format(info['title'], info['home'][0], ''))

        # description
        entry.append('')

        # download
        field = 'download'
        if field in info and info[field]:
            entry.append('<a href="{}">Link</a>'.format(info[field][0]))
        else:
            entry.append('')

        # state (field state is essential)
        entry.append('{} / {}'.format(info['state'][0], 'inactive since {}'.format(info['inactive']) if 'inactive' in info else 'active'))

        # keywords
        field = 'keywords'
        if field in info and info[field]:
            entry.append(', '.join(info[field]))
        else:
            entry.append('')

        # source
        text = ''
        entry.append(text)

        # append to entries
        entries.append(entry)

    # sort entries by game name
    entries.sort(key=lambda x: x[0])

    db['data'] = entries

    # output
    json_path = os.path.join(games_path, os.path.pardir, 'docs', 'data.json')
    text = json.dumps(db, indent=1)
    write_text(json_path, text)


def git_repo(repo):
    """
        Tests if a repo is a git repo, then returns the repo url, possibly modifying it slightly (for Github).
    """

    # for github we check that the url is github.com/user/repo and add .git
    github = 'https://github.com/'
    if repo.startswith(github):
        if len(repo.split('/')) == 5:
            return repo + '.git'

    # for all others we just check if they start with the typical urls of git services

    # 'https://git.code.sf.net/p/' currently doesn't work that well
    services = ['https://git.tuxfamily.org/', 'http://git.pond.sub.org/', 'https://gitorious.org/']
    for service in services:
        if repo.startswith(service):
            return repo

    # generic (https://*.git) or (http://*.git) ending on git
    if (repo.startswith('https://') or repo.startswith('http://')) and repo.endswith('.git'):
        return repo

    # the rest is ignored
    return None


def update_primary_code_repositories():

    primary_repos = []

    # for every entry filter those that are known git repositories (add additional repositories)
    for info in infos.values():
        field = 'code repository-raw'
        # if field 'Code repository' is available
        if field in info:
            repos = info[field]
            if repos:
                # split at comma
                repos = repos.split(',')
                # keep the first and all others containing "(+)"
                additional_repos = [x for x in repos[1:] if "(+)" in x]
                repos = repos[0:1]
                repos.extend(additional_repos)
                for repo in repos:
                    # remove parenthesis and strip of white spaces
                    repo = re.sub(r'\([^)]*\)', '', repo)
                    repo = repo.strip()
                    repo = git_repo(repo)
                    if repo:
                        primary_repos.append(repo)

    # sort them alphabetically (and remove duplicates)
    primary_repos = sorted(set(primary_repos))

    # write them to tools/git
    json_path = os.path.join(games_path, os.path.pardir, 'tools', 'git_archive', 'archives.json')
    text = json.dumps(primary_repos, indent=1)
    write_text(json_path, text)

if __name__ == "__main__":

    # paths
    games_path = os.path.realpath(os.path.join(os.path.dirname(__file__), os.path.pardir, 'games'))
    readme_file = os.path.realpath(os.path.join(games_path, os.pardir, 'README.md'))

    # assemble info
    infos = assemble_infos()

    # recount and write to readme
    update_readme()

    # generate list in toc files
    update_category_tocs()

    # generate report
    generate_statistics()

    # update database for html table
    export_json()

    # check for unfilled template lines
    check_template_leftovers()

    # check external links (only rarely)
    # check_validity_external_links()

    # collect list of primary code repositories
    update_primary_code_repositories()