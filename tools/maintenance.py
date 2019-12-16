"""
    Runs a series of maintenance operations on the collection of entry files, updating the table of content files for
    each category as well as creating a statistics file.

    Counts the number of records each sub-folder and updates the overview.
    Sorts the entries in the contents files of each sub folder alphabetically.

    This script runs with Python 3, it could also with Python 2 with some minor tweaks probably.
"""

import urllib.request
import http.client
import datetime
import json
import textwrap
import os
import re
from utils import constants as c, utils, osg


def update_readme_and_tocs(infos):
    """
    Recounts entries in sub categories and writes them to the readme.
    Also updates the _toc files in the categories directories.

    Note: The Readme must have a specific structure at the beginning, starting with "# Open Source Games" and ending
    on "A collection.."

    Needs to be performed regularly.
    """
    print('update readme and toc files')

    # completely delete content of toc path
    for file in os.listdir(c.tocs_path):
        os.remove(os.path.join(c.tocs_path, file))

    # read readme
    readme_file = os.path.join(c.root_path, 'README.md')
    readme_text = utils.read_text(readme_file)

    # compile regex for identifying the building blocks in the readme
    regex = re.compile(r"(.*?)(\[comment\]: # \(start.*?end of autogenerated content\))(.*)", re.DOTALL)

    # apply regex
    matches = regex.findall(readme_text)
    if len(matches) != 1:
        raise RuntimeError('readme file has invalid structure')
    matches = matches[0]
    start = matches[0]
    end = matches[2]

    tocs_text = ''

    # split infos
    infos_games, infos_tools, infos_frameworks, infos_libraries = osg.split_infos(infos)

    # create games, tools, frameworks, libraries tocs
    title = 'Games'
    file = '_games.md'
    tocs_text += '**[{}](entries/tocs/{}#{})** ({}) - '.format(title, file, title, len(infos_games))
    create_toc(title, file, infos_games)

    title = 'Tools'
    file = '_tools.md'
    tocs_text += '**[{}](entries/tocs/{}#{})** ({}) - '.format(title, file, title, len(infos_tools))
    create_toc(title, file, infos_tools)

    title = 'Frameworks'
    file = '_frameworks.md'
    tocs_text += '**[{}](entries/tocs/{}#{})** ({}) - '.format(title, file, title, len(infos_frameworks))
    create_toc(title, file, infos_frameworks)

    title = 'Libraries'
    file = '_libraries.md'
    tocs_text += '**[{}](entries/tocs/{}#{})** ({})\n'.format(title, file, title, len(infos_libraries))
    create_toc(title, file, infos_libraries)

    # create by category
    categories_text = []
    for keyword in osg.recommended_keywords:
        infos_filtered = [x for x in infos if keyword in x['keywords']]
        title = keyword.capitalize()
        name = keyword.replace(' ', '-')
        file = '_{}.md'.format(name)
        categories_text.append('**[{}](entries/tocs/{}#{})** ({})'.format(title, file, name, len(infos_filtered)))
        create_toc(title, file, infos_filtered)
    categories_text.sort()
    tocs_text += '\nBy category: {}\n'.format(', '.join(categories_text))

    # create by platform
    platforms_text = []
    for platform in osg.valid_platforms:
        infos_filtered = [x for x in infos if platform in x.get('platform', [])]
        title = platform
        name = platform.lower()
        file = '_{}.md'.format(name)
        platforms_text.append('**[{}](entries/tocs/{}#{})** ({})'.format(title, file, name, len(infos_filtered)))
        create_toc(title, file, infos_filtered)
    tocs_text += '\nBy platform: {}\n'.format(', '.join(platforms_text))

    # insert new text in the middle (the \n before the second comment is necessary, otherwise Markdown displays it as part of the bullet list)
    text = start + "[comment]: # (start of autogenerated content, do not edit)\n" + tocs_text + "\n[comment]: # (end of autogenerated content)" + end

    # write to readme
    utils.write_text(readme_file, text)


def create_toc(title, file, entries):
    """

    """
    # file path
    toc_file = os.path.join(c.tocs_path, file)

    # header line
    text = '[comment]: # (autogenerated content, do not edit)\n# {}\n\n'.format(title)

    # assemble rows
    rows = []
    for entry in entries:
        rows.append('- **[{}]({})** ({})'.format(entry['name'], '../' + entry['file'], ', '.join(entry['code language'] + entry['code license'] + entry['state'])))

    # sort rows (by title)
    rows.sort(key=str.casefold)

    # add to text
    text += '\n'.join(rows)

    # write to toc file
    utils.write_text(toc_file, text)


def check_validity_external_links():
    """
    Checks all external links it can find for validity. Prints those with non OK HTTP responses. Does only need to be run
    from time to time.
    """

    # TODO check if links are occurring in multiple entries, first go through all entries and find all links, then check links for multiple entries, then check links, follow redirects

    print("check external links (can take a while)")

    # regex for finding urls (can be in <> or in ]() or after a whitespace
    regex = re.compile(r"[\s\n]<(http.+?)>|\]\((http.+?)\)|[\s\n](http[^\s\n,]+?)[\s\n\)]")
    # regex = re.compile(r"[\s\n<(](http://.*?)[\s\n>)]")

    # count
    number_checked_links = 0

    # ignore the following urls (they give false positives here)
    ignored_urls = ('https://git.tukaani.org/xz.git')

    # iterate over all entries
    for _, entry_path, content in osg.entry_iterator():

            # apply regex
            matches = regex.findall(content)

            # for each match
            for match in matches:

                # for each possible clause
                for url in match:

                    # if there was something (and not a sourceforge git url)
                    if url and not url.startswith('https://git.code.sf.net/p/') and url not in ignored_urls:
                        try:
                            # without a special header, frequent 403 responses occur
                            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64)'})
                            urllib.request.urlopen(req)
                        except urllib.error.HTTPError as e:
                            print("{}: {} - {}".format(os.path.basename(entry_path), url, e.code))
                        except urllib.error.URLError as e:
                            print("{}: {} - {}".format(os.path.basename(entry_path), url, e.reason))
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

    print('check for template leftovers')

    # load template and get all lines
    text = utils.read_text(os.path.join(c.root_path, 'template.md'))
    text = text.split('\n')
    check_strings = [x for x in text if x and not x.startswith('##')]

    # iterate over all entries
    for _, entry_path, content in osg.entry_iterator():

        for check_string in check_strings:
            if content.find(check_string) >= 0:
                raise RuntimeError('{}: found {}'.format(os.path.basename(entry_path), check_string))


def fix_entries():
    """
    Fixes the keywords, code dependencies, build systems, .. entries, mostly by automatically sorting them.
    """

    keyword_synonyms = {'RTS': ('real time', 'strategy'), 'realtime': 'real time'}

    # TODO also sort other fields, only read once and then do all, move to separate file
    # example Javascript to JavaScript and then add whenever the known languages check hits

    print('fix entries')

    # keywords
    regex = re.compile(r"(.*)- Keywords:([^\n]*)(.*)", re.DOTALL)

    # iterate over all entries
    for entry, entry_path, content in osg.entry_iterator():

        # match with regex
        matches = regex.findall(content)
        if len(matches) != 1:
            raise RuntimeError('Could not find keywords in entry "{}"'.format(entry))

        match = matches[0]

        # get elements out, split, strip, delete duplicates
        elements = match[1].split(',')
        elements = [x.strip() for x in elements]
        elements = list(set(elements))

        # get category out
        for keyword in osg.recommended_keywords:
            if keyword in elements:
                elements.remove(keyword)
                category = keyword
                break

        # special treatments here
        elements = [x if x != 'TBS' and x != 'TB' else 'turn based' for x in elements]
        elements = [x if x != 'RTS' else 'real time' for x in elements]
        elements = [x if x != 'MMO' else 'massive multiplayer online' for x in elements]
        elements = [x if x != 'MMO' else 'multiplayer online' for x in elements]
        elements = [x if x != 'SP' else 'singleplayer' for x in elements]
        elements = [x if x != 'MP' else 'multiplayer' for x in elements]
        elements = [x if x != 'engine' else 'game engine' for x in elements]
        elements = [x if x != 'rpg' else 'role playing' for x in elements]
        elements = [x if x != 'turn based' else 'turn-based' for x in elements]
        for keyword in ('browser', 'misc', 'tools'):
            if keyword in elements:
                elements.remove(keyword)

        # sort
        elements.sort(key=str.casefold)

        # add category
        elements.insert(0, category)

        keywords = '- Keywords: {}'.format(', '.join(elements))

        new_content = match[0] + keywords + match[2]

        if new_content != content:
            # write again
            utils.write_text(entry_path, new_content)

    # code dependencies
    regex = re.compile(r"(.*)- Code dependencies:([^\n]*)(.*)", re.DOTALL)

    # iterate over all entries
    for entry, entry_path, content in osg.entry_iterator():
        # match with regex
        matches = regex.findall(content)

        if not matches:
            # no code dependencies given
            continue

        match = matches[0]

        # get code dependencies out, split, strip, delete duplicates
        elements = match[1].split(',')
        elements = [x.strip() for x in elements]
        elements = list(set(elements))

        # special treatments here
        elements = [x if x != 'Blender' else 'Blender game engine' for x in elements]
        elements = [x if x.lower() != 'libgdx' else 'libGDX' for x in elements]
        elements = [x if x != 'SDL 2' else 'SDL2' for x in elements]
        elements = [x if x.lower() != "ren'py" else "Ren'Py" for x in elements]

        # sort
        elements.sort(key=str.casefold)

        code_dependencies = '- Code dependencies: {}'.format(', '.join(elements))

        new_content = match[0] + code_dependencies + match[2]

        if new_content != content:
            # write again
            utils.write_text(entry_path, new_content)

    # build systems
    regex = re.compile(r"(.*)- Build system:([^\n]*)(.*)", re.DOTALL)

    # iterate over all entries
    for entry, entry_path, content in osg.entry_iterator():
        # match with regex
        matches = regex.findall(content)

        if not matches:
            # no build system given
            continue

        match = matches[0]

        # get code dependencies out, split, strip, delete duplicates
        elements = match[1].split(',')
        elements = [x.strip() for x in elements]
        elements = list(set(elements))

        # special treatments here

        # sort
        elements.sort(key=str.casefold)

        build_system = '- Build system: {}'.format(', '.join(elements))

        new_content = match[0] + build_system + match[2]

        if new_content != content:
            # write again
            utils.write_text(entry_path, new_content)


def update_statistics(infos):
    """
    Generates the statistics page.

    Should be done every time the entries change.
    """

    print('update statistics')

    # start the page
    statistics_file = os.path.join(c.root_path, 'statistics.md')
    statistics = '[comment]: # (autogenerated content, do not edit)\n# Statistics\n\n'

    # total number
    number_entries = len(infos)
    rel = lambda x: x / number_entries * 100 # conversion to percent

    statistics += 'analyzed {} entries on {}\n\n'.format(number_entries, datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    # State (beta, mature, inactive)
    statistics += '## State\n\n'

    number_state_beta = sum(1 for x in infos if 'beta' in x['state'])
    number_state_mature = sum(1 for x in infos if 'mature' in x['state'])
    number_inactive = sum(1 for x in infos if 'inactive' in x)
    statistics += '- mature: {} ({:.1f}%)\n- beta: {} ({:.1f}%)\n- inactive: {} ({:.1f}%)\n\n'.format(number_state_mature, rel(number_state_mature), number_state_beta, rel(number_state_beta), number_inactive, rel(number_inactive))

    if number_inactive > 0:
        entries_inactive = [(x['name'], x['inactive']) for x in infos if 'inactive' in x]
        entries_inactive.sort(key=lambda x: str.casefold(x[0]))  # first sort by name
        entries_inactive.sort(key=lambda x: x[1], reverse=True) # then sort by inactive year (more recently first)
        entries_inactive = ['{} ({})'.format(*x) for x in entries_inactive]
        statistics += '##### Inactive State\n\n' + ', '.join(entries_inactive) + '\n\n'

    # Language
    statistics += '## Code Languages\n\n'
    field = 'code language'

    # those without language tag
    # TODO the language tag is now an essential field, this cannot happen anymore
    # number_no_language = sum(1 for x in infois if field not in x)
    # if number_no_language > 0:
    #     statistics += 'Without language tag: {} ({:.1f}%)\n\n'.format(number_no_language, rel(number_no_language))
    #     entries_no_language = [x['name'] for x in infois if field not in x]
    #     entries_no_language.sort()
    #     statistics += ', '.join(entries_no_language) + '\n\n'

    # get all languages together
    languages = []
    for info in infos:
        if field in info:
            languages.extend(info[field])

    unique_languages = set(languages)
    unique_languages = [(l, languages.count(l) / len(languages)) for l in unique_languages]
    unique_languages.sort(key=lambda x: str.casefold(x[0])) # first sort by name
    unique_languages.sort(key=lambda x: x[1], reverse=True) # then sort by occurrence (highest occurrence first)
    unique_languages = ['- {} ({:.1f}%)\n'.format(x[0], x[1]*100) for x in unique_languages]
    statistics += '##### Language frequency\n\n' + ''.join(unique_languages) + '\n'

    # Licenses
    statistics += '## Code licenses\n\n'
    field = 'code license'

    # those without license
    number_no_license = sum(1 for x in infos if field not in x)
    if number_no_license > 0:
        statistics += 'Without license tag: {} ({:.1f}%)\n\n'.format(number_no_license, rel(number_no_license))
        entries_no_license = [x['name'] for x in infos if field not in x]
        entries_no_license.sort()
        statistics += ', '.join(entries_no_license) + '\n\n'

    # get all licenses together
    licenses = []
    for info in infos:
        if field in info:
            licenses.extend(info[field])

    unique_licenses = set(licenses)
    unique_licenses = [(l, licenses.count(l) / len(licenses)) for l in unique_licenses]
    unique_licenses.sort(key=lambda x: str.casefold(x[0])) # first sort by name
    unique_licenses.sort(key=lambda x: -x[1]) # then sort by occurrence (highest occurrence first)
    unique_licenses = ['- {} ({:.1f}%)\n'.format(x[0], x[1]*100) for x in unique_licenses]
    statistics += '##### Licenses frequency\n\n' + ''.join(unique_licenses) + '\n'

    # Keywords
    statistics += '## Keywords\n\n'
    field = 'keywords'

    # get all keywords together
    keywords = []
    for info in infos:
        if field in info:
            keywords.extend(info[field])
    # reduce those starting with "inspired by"
    keywords = [x if not x.startswith('inspired by') else 'inspired' for x in keywords]
    # reduce those starting with "multiplayer"
    keywords = [x if not x.startswith('multiplayer') else 'multiplayer' for x in keywords]

    unique_keywords = set(keywords)
    unique_keywords = [(l, keywords.count(l) / len(keywords)) for l in unique_keywords]
    unique_keywords.sort(key=lambda x: str.casefold(x[0])) # first sort by name
    unique_keywords.sort(key=lambda x: -x[1]) # then sort by occurrence (highest occurrence first)
    unique_keywords = ['- {} ({:.1f}%)'.format(x[0], x[1]*100) for x in unique_keywords]
    statistics += '##### Keywords frequency\n\n' + '\n'.join(unique_keywords) + '\n\n'

    # no download or play field
    statistics += '## Entries without download or play fields\n\n'

    entries = []
    for info in infos:
        if 'download' not in info and 'play' not in info:
            entries.append(info['name'])
    entries.sort(key=str.casefold)
    statistics +=  '{}: '.format(len(entries)) + ', '.join(entries) + '\n\n'

    # code hosted not on github, gitlab, bitbucket, launchpad, sourceforge
    popular_code_repositories = ('github.com', 'gitlab.com', 'bitbucket.org', 'code.sf.net', 'code.launchpad.net')
    statistics += '## Entries with a code repository not on a popular site\n\n'

    entries = []
    field = 'code repository'
    for info in infos:
        if field in info:
            popular = False
            for repo in info[field]:
                for popular_repo in popular_code_repositories:
                    if popular_repo in repo:
                        popular = True
                        break
            # if there were repositories, but none popular, add them to the list
            if not popular:
                entries.append(info['name'])
                # print(info[field])
    entries.sort(key=str.casefold)
    statistics += '{}: '.format(len(entries)) + ', '.join(entries) + '\n\n'

    # Code dependencies
    statistics += '## Code dependencies\n\n'
    field = 'code dependencies'

    # get all code dependencies together
    code_dependencies = []
    entries_with_code_dependency = 0
    for info in infos:
        if field in info:
            code_dependencies.extend(info[field])
            entries_with_code_dependency += 1
    statistics += 'With code dependency field {} ({:.1f}%)\n\n'.format(entries_with_code_dependency, rel(entries_with_code_dependency))

    unique_code_dependencies = set(code_dependencies)
    unique_code_dependencies = [(l, code_dependencies.count(l) / len(code_dependencies)) for l in unique_code_dependencies]
    unique_code_dependencies.sort(key=lambda x: str.casefold(x[0])) # first sort by name
    unique_code_dependencies.sort(key=lambda x: -x[1]) # then sort by occurrence (highest occurrence first)
    unique_code_dependencies = ['- {} ({:.1f}%)'.format(x[0], x[1]*100) for x in unique_code_dependencies]
    statistics += '##### Code dependencies frequency\n\n' + '\n'.join(unique_code_dependencies) + '\n\n'

    # Build systems:
    statistics += '## Build systems\n\n'
    field = 'build system'

    # get all build systems together
    build_systems = []
    for info in infos:
        if field in info:
            build_systems.extend(info[field])

    statistics += 'Build systems information available for {:.1f}% of all projects.\n\n'.format(rel(len(build_systems)))

    unique_build_systems = set(build_systems)
    unique_build_systems = [(l, build_systems.count(l) / len(build_systems)) for l in unique_build_systems]
    unique_build_systems.sort(key=lambda x: str.casefold(x[0])) # first sort by name
    unique_build_systems.sort(key=lambda x: -x[1]) # then sort by occurrence (highest occurrence first)
    unique_build_systems = ['- {} ({:.1f}%)'.format(x[0], x[1]*100) for x in unique_build_systems]
    statistics += '##### Build systems frequency ({})\n\n'.format(len(build_systems)) + '\n'.join(unique_build_systems) + '\n\n'

    # C, C++ projects without build system information
    c_cpp_project_without_build_system = []
    for info in infos:
        if field not in info and ('C' in info['code language'] or 'C++' in info['code language']):
            c_cpp_project_without_build_system.append(info['name'])
    c_cpp_project_without_build_system.sort(key=str.casefold)
    statistics += '##### C and C++ projects without build system information ({})\n\n'.format(len(c_cpp_project_without_build_system)) + ', '.join(c_cpp_project_without_build_system) + '\n\n'

    # C, C++ projects with build system information but without CMake as build system
    c_cpp_project_not_cmake = []
    for info in infos:
        if field in info and 'CMake' in info[field] and ('C' in info['code language'] or 'C++' in info['code language']):
            c_cpp_project_not_cmake.append(info['name'])
    c_cpp_project_not_cmake.sort(key=str.casefold)
    statistics += '##### C and C++ projects with a build system different from CMake ({})\n\n'.format(len(c_cpp_project_not_cmake)) + ', '.join(c_cpp_project_not_cmake) + '\n\n'

    # Platform
    statistics += '## Platform\n\n'
    field = 'platform'

    # get all platforms together
    platforms = []
    for info in infos:
        if field in info:
            platforms.extend(info[field])

    statistics += 'Platform information available for {:.1f}% of all projects.\n\n'.format(rel(len(platforms)))

    unique_platforms = set(platforms)
    unique_platforms = [(l, platforms.count(l) / len(platforms)) for l in unique_platforms]
    unique_platforms.sort(key=lambda x: str.casefold(x[0])) # first sort by name
    unique_platforms.sort(key=lambda x: -x[1]) # then sort by occurrence (highest occurrence first)
    unique_platforms = ['- {} ({:.1f}%)'.format(x[0], x[1]*100) for x in unique_platforms]
    statistics += '##### Platforms frequency\n\n' + '\n'.join(unique_platforms) + '\n\n'

    # write to statistics file
    utils.write_text(statistics_file, statistics)


def export_json(infos):
    """
    Parses all entries, collects interesting info and stores it in a json file suitable for displaying
    with a dynamic table in a browser.
    """

    print('export to json for web display')

    # make database out of it
    db = {'headings': ['Game', 'Description', 'Download', 'State', 'Keywords', 'Source']}

    entries = []
    for info in infos:

        # game & description
        entry = ['{} (<a href="{}">home</a>, <a href="{}">entry</a>)'.format(info['name'], info['home'][0],
            r'https://github.com/Trilarion/opensourcegames/blob/master/entries/' + info['file']),
            textwrap.shorten(info['description'], width=60, placeholder='..')]

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
        text = []
        field = 'code repository'
        if field in info and info[field]:
            text.append('<a href="{}">Source</a>'.format(info[field][0]))
        field = 'code language'
        if field in info and info[field]:
            text.append(', '.join(info[field]))
        field = 'code license'
        if field in info and info[field]:
            text.append(info[field][0])
        entry.append(' - '.join(text))

        # append to entries
        entries.append(entry)

    # sort entries by game name
    entries.sort(key=lambda x: str.casefold(x[0]))

    db['data'] = entries

    # output
    json_path = os.path.join(c.entries_path, os.path.pardir, 'docs', 'data.json')
    text = json.dumps(db, indent=1)
    utils.write_text(json_path, text)


def git_repo(repo):
    """
        Tests if a repo is a git repo, then returns the repo url, possibly modifying it slightly.
    """

    # generic (https://*.git) or (http://*.git) ending on git
    if (repo.startswith('https://') or repo.startswith('http://')) and repo.endswith('.git'):
        return repo

    # for all others we just check if they start with the typical urls of git services
    services = ['https://git.tuxfamily.org/', 'http://git.pond.sub.org/', 'https://gitorious.org/', 'https://git.code.sf.net/p/']
    for service in services:
        if repo.startswith(service):
            return repo

    if repo.startswith('git://'):
        return repo

    # the rest is ignored
    return None


def svn_repo(repo):
    """
    
    """
    if repo.startswith('https://svn.code.sf.net/p/'):
        return repo

    if repo.startswith('http://svn.uktrainsim.com/svn/'):
        return repo

    if repo is 'https://rpg.hamsterrepublic.com/source/wip':
        return repo

    if repo.startswith('http://svn.savannah.gnu.org/svn/'):
        return repo

    if repo.startswith('svn://'):
        return repo

    if repo.startswith('https://svn.icculus.org/') or repo.startswith('http://svn.icculus.org/'):
        return repo
    
    # not svn
    return None


def hg_repo(repo):
    """

    """
    if repo.startswith('https://bitbucket.org/') and not repo.endswith('.git'):
        return repo

    if repo.startswith('http://hg.'):
        return repo

    # not hg
    return None


def export_primary_code_repositories_json(infos):
    """

    """

    print('export to json for local repository update')

    primary_repos = {'git': [], 'svn': [], 'hg': []}
    unconsumed_entries = []

    # for every entry filter those that are known git repositories (add additional repositories)
    field = 'code repository-raw'
    for info in infos:
        # if field 'Code repository' is available
        if field in info:
            consumed = False
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
                    url = git_repo(repo)
                    if url:
                        primary_repos['git'].append(url)
                        consumed = True
                        continue
                    url = svn_repo(repo)
                    if url:
                        primary_repos['svn'].append(url)
                        consumed = True
                        continue
                    url = hg_repo(repo)
                    if url:
                        primary_repos['hg'].append(url)
                        consumed=True
                        continue

            if not consumed:
                unconsumed_entries.append([info['name'], info[field]])
                # print output
                if 'code repository' in info:
                    print('Entry "{}" unconsumed repo: {}'.format(info['name'], info[field]))

    # sort them alphabetically (and remove duplicates)
    for k, v in primary_repos.items():
        primary_repos[k] = sorted(set(v))

    # statistics of gits
    git_repos = primary_repos['git']
    print('{} Git repositories'.format(len(git_repos)))
    for domain in ('repo.or.cz', 'anongit.kde.org', 'bitbucket.org', 'git.code.sf.net', 'git.savannah', 'git.tuxfamily', 'github.com', 'gitlab.com', 'gitlab.com/osgames', 'gitlab.gnome.org'):
        print('{} on {}'.format(sum(1 if domain in x else 0 for x in git_repos), domain))

    # write them to tools/git
    json_path = os.path.join(c.root_path, 'tools', 'archives.json')
    text = json.dumps(primary_repos, indent=1)
    utils.write_text(json_path, text)


def export_git_code_repositories_json():
    """

    """

    urls = []
    field = 'code repository'

    # for every entry, get all git
    for info in infos:
        # if field 'Code repository' is available
        if field in info:
            repos = info[field]
            if repos:
                # take the first
                repo = repos[0]
                url = git_repo(repo)
                if url:
                    urls.append(url)

    # sort them alphabetically (and remove duplicates)
    urls.sort()

    # write them to tools/git
    json_path = os.path.join(c.root_path, 'tools', 'git_repositories.json')
    text = json.dumps(urls, indent=1)
    utils.write_text(json_path, text)


def sort_text_file(file, name):
    """
    Reads a text file, splits in lines, removes duplicates, sort, writes back.
    """
    text = utils.read_text(file)
    text = text.split('\n')
    text = sorted(list(set(text)), key=str.casefold)
    print('{} contains {} items'.format(name, len(text)))
    text = '\n'.join(text)
    utils.write_text(file, text)


def clean_backlog(stripped_game_urls):

    # read backlog and split
    file = os.path.join(c.root_path, 'tools', 'backlog.txt')
    text = utils.read_text(file)
    text = text.split('\n')

    # remove those that are in stripped_game_urls
    text = [x for x in text if utils.strip_url(x) not in stripped_game_urls]

    # remove duplicates and sort
    text = sorted(list(set(text)), key=str.casefold)
    print('backlog contains {} items'.format(len(text)))

    # join and save again
    text = '\n'.join(text)
    utils.write_text(file, text)


def check_validity_backlog():
    import requests

    # read backlog and split
    file = os.path.join(c.root_path, 'tools', 'backlog.txt')
    text = utils.read_text(file)
    urls = text.split('\n')
    urls = [x.split(' ')[0] for x in urls]

    headers = {'user-agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64)'}
    for url in urls:
        try:
            r = requests.get(url, headers=headers, timeout=5)
        except Exception as e:
            print('{} gave error: {}'.format(url, e))
        else:
            if r.status_code != requests.codes.ok:
                print('{} returned status code: {}'.format(url, r.status_code))

            if r.is_redirect or r.history:
                print('{} redirected to {}, {}'.format(url, r.url, r.history))


def update_inspirations(infos):
    """

    """

    print('update inspirations')

    inspirations_file = os.path.join(c.root_path, 'inspirations.md')
    inspirations = '[comment]: # (partly autogenerated content, edit with care, read the manual before)\n# Inspirations\n\n'

    # collect information
    originals = {}
    for info in infos:
        name = info['name']
        keywords = info['keywords']
        ins = [x[12:] for x in keywords if x.startswith('inspired by ')]
        if ins:
            ins = ins[0].split(' + ')
            for original in ins:
                if original in originals:
                    originals[original].append(name)
                else:
                    originals[original] = [name]

    # number of inspirations
    inspirations += '{} games listed as inspirations.\n\n'.format(len(originals))

    # iterate through originals alphabetically sorted
    for original, names in sorted(originals.items(), key=lambda x: str.casefold(x[0])):
        inspirations += '## {} ({})\n\n'.format(original, len(names))
        inspirations += '- Inspired entries: {}\n\n'.format(', '.join(sorted(names, key=str.casefold)))

    # write to statistics file
    utils.write_text(inspirations_file, inspirations)


def update_developer(infos):
    """

    """

    print('update developer')

    developer_file = os.path.join(c.root_path, 'developer.md')
    content = '[comment]: # (partly autogenerated content, edit with care, read the manual before)\n# Developer\n\n'

    # collect information
    developer = {}
    for info in infos:
        if 'developer' in info:
            name = info['name']
            devs = info['developer']
            for dev in devs:
                if dev in developer:
                    developer[dev].append(name)
                else:
                    developer[dev] = [name]

    # number of developers
    content += '{} listed developer(s).\n\n'.format(len(developer))

    # iterate through developers alphabetically sorted
    for dev, names in sorted(developer.items(), key=lambda x: str.casefold(x[0])):
        content += '## {} ({})\n\n'.format(dev, len(names))
        content += '- Games: {}\n\n'.format(', '.join(sorted(names, key=str.casefold)))

    # write to statistics file
    utils.write_text(developer_file, content)


def check_code_dependencies(infos):
    """

    """

    # get all names
    names = [x['name'] for x in infos]

    # TODO get all names of frameworks and libraries only and use osg.code_dependencies_aliases

    # get all code dependencies
    dependencies = {}
    for info in infos:
        deps = info.get('code dependencies', [])
        for dependency in deps:
            if dependency in dependencies:
                dependencies[dependency] += 1
            else:
                dependencies[dependency] = 1

    # delete those that are in names
    dependencies = [(k, v) for k,v in dependencies.items() if k not in names and k not in osg.code_dependencies_without_entry]

    # sort by number
    dependencies.sort(key=lambda x: x[1], reverse=True)

    # print out
    print('Code dependencies not included as entry')
    for dep in dependencies:
        print('{} ({})'.format(*dep))


if __name__ == "__main__":

    # check_validity_backlog()

    # backlog
    game_urls = osg.extract_links()
    text = utils.read_text(os.path.join(c.root_path, 'tools', 'rejected.txt'))
    regex = re.compile(r"\((http.*?)\)", re.MULTILINE)
    matches = regex.findall(text)
    rejected_urls = []
    for match in matches:
        urls = match.split(',')
        urls = [x.strip() for x in urls]
        rejected_urls.extend(urls)
    game_urls.extend(rejected_urls)
    more_urls = []
    for url in game_urls:
        if url.startswith('https://web.archive.org/web'):
            # print(url) # sometimes the http is missing in archive links (would need proper parsing)
            url = url[url.index('http', 5):]
            more_urls.append(url)
    game_urls.extend(more_urls)
    stripped_game_urls = [utils.strip_url(x) for x in game_urls]
    clean_backlog(stripped_game_urls)

    # check for unfilled template lines
    check_template_leftovers()

    # fix entries
    fix_entries()

    # assemble info
    infos = osg.assemble_infos()

    # recount and write to readme and to tocs
    update_readme_and_tocs(infos)

    # generate report
    update_statistics(infos)

    # update inspirations
    update_inspirations(infos)

    # update developers
    update_developer(infos)

    # update database for html table
    export_json(infos)

    # collect list of primary code repositories
    export_primary_code_repositories_json(infos)

    # check code dependencies
    check_code_dependencies(infos)

    # collect list of git code repositories (only one per project) for git_statistics script
    # export_git_code_repositories_json()

    # check external links (only rarely)
    # check_validity_external_links()

    # sort backlog and rejected
    # sort_text_file(os.path.join(c.root_path, 'tools', 'backlog.txt'), 'backlog')
    sort_text_file(os.path.join(c.root_path, 'tools', 'rejected.txt'), 'rejected games list')
