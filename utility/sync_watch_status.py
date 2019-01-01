#!/usr/bin/env python
"""
Description: Sync the watch status from one user to another. Either by user or user/libraries
Author: Blacktwin
Requires: requests, plexapi, argparse

Enabling Scripts in Tautulli:
Taultulli > Settings > Notification Agents > Add a Notification Agent > Script

Configuration:
Taultulli > Settings > Notification Agents > New Script > Configuration:

 Script Name: sync_watch_status.py
 Set Script Timeout: default
 Description: Sync watch status
 Save

Triggers:
Taultulli > Settings > Notification Agents > New Script > Triggers:

 Check: Notify on Watched
 Save

Conditions:
Taultulli > Settings > Notification Agents > New Script > Conditions:

 Set Conditions: [{username} | {is} | {user_to_sync_from} ]
 Save

Script Arguments:
Taultulli > Settings > Notification Agents > New Script > Script Arguments:

 Select: Notify on Watched
 Arguments: --ratingKey {rating_key} --userTo "Username2" "Username3" --userFrom {username}

 Save
 Close

 Example:
    Set in Tautulli in script notification agent or run manually

    plex_api_share.py --userFrom USER1 --userTo USER2 --libraries Movies
       - Synced watch status of {title from library} to {USER2}'s account.

    plex_api_share.py --userFrom USER1 --userTo USER2 USER3 --allLibraries
       - Synced watch status of {title from library} to {USER2 or USER3}'s account.

    Excluding;
    --libraries becomes excluded if --allLibraries is set
    sync_watch_status.py --userFrom USER1 --userTo USER2 --allLibraries --libraries Movies
       - Shared [all libraries but Movies] with USER.

"""
import requests
import argparse
from plexapi.server import PlexServer, CONFIG

# Using CONFIG file
PLEX_URL = ''
PLEX_TOKEN = ''

if not PLEX_URL:
    PLEX_URL = CONFIG.data['auth'].get('server_baseurl', '')

if not PLEX_TOKEN:
    PLEX_TOKEN = CONFIG.data['auth'].get('server_token', '')


sess = requests.Session()
# Ignore verifying the SSL certificate
sess.verify = False  # '/path/to/certfile'
# If verify is set to a path to a directory,
# the directory must have been processed using the c_rehash utility supplied
# with OpenSSL.
if sess.verify is False:
    # Disable the warning that the request is insecure, we know that...
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

plex = PlexServer(PLEX_URL, PLEX_TOKEN, session=sess)

sections_lst = [x.title for x in plex.library.sections()]
user_lst = [x.title for x in plex.myPlexAccount().users()]
# Adding admin account name to list
user_lst.append(plex.myPlexAccount().title)

def get_account(user):
    if user == plex.myPlexAccount().title:
        server = plex
    else:
        # Access Plex User's Account
        userAccount = plex.myPlexAccount().user(user)
        token = userAccount.get_token(plex.machineIdentifier)
        server = PlexServer(PLEX_URL, token)
    return server


def mark_watached(sectionFrom, accountTo, userTo):
    # Check sections for watched items
    for item in sectionFrom.search(unwatched=False):
        title = item.title.encode('utf-8')
        # Check movie media type
        if item.type == 'movie':
            accountTo.fetchItem(item.key).markWatched()
            print('Synced watch status of {} to {}\'s account.'.format(title, userTo))
        # Check show media type
        elif item.type == 'show':
            for episode in sectionFrom.searchEpisodes(unwatched=False, title=title):
                ep_title = episode.title.encode('utf-8')
                accountTo.fetchItem(episode.key).markWatched()
                print('Synced watch status of {} - {} to {}\'s account.'.format(title, ep_title, userTo))


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description="Sync watch status from one user to others.",
                                     formatter_class=argparse.RawTextHelpFormatter)
    requiredNamed = parser.add_argument_group('required named arguments')
    parser.add_argument('--libraries', nargs='*', choices=sections_lst, metavar='library',
                        help='Space separated list of case sensitive names to process. Allowed names are: \n'
                             '(choices: %(choices)s)')
    parser.add_argument('--allLibraries', action='store_true',
                        help='Select all libraries.')
    parser.add_argument('--ratingKey', nargs=1,
                        help='Rating key of item whose watch status is to be synced.')
    requiredNamed.add_argument('--userFrom', choices=user_lst, metavar='username', required=True,
                        help='Space separated list of case sensitive names to process. Allowed names are: \n'
                             '(choices: %(choices)s)')
    requiredNamed.add_argument('--userTo', nargs='*', choices=user_lst, metavar='usernames', required=True,
                        help='Space separated list of case sensitive names to process. Allowed names are: \n'
                             '(choices: %(choices)s)')

    opts = parser.parse_args()
    # print(opts)

    # Create Sync-From user account
    plexFrom = get_account(opts.userFrom)

    # Defining libraries
    libraries = ''
    if opts.allLibraries and not opts.libraries:
        libraries = sections_lst
    elif not opts.allLibraries and opts.libraries:
        libraries = opts.libraries
    elif opts.allLibraries and opts.libraries:
        # If allLibraries is used then any libraries listed will be excluded
        for library in opts.libraries:
            sections_lst.remove(library)
            libraries = sections_lst

    # Go through list of users
    for user in opts.userTo:
        # Create Sync-To user account
        plexTo = get_account(user)
        if libraries:
            # Go through Libraries
            for library in libraries:
                try:
                    print('Checking library: {}'.format(library))
                    # Check library for watched items
                    section = plexFrom.library.section(library)
                    mark_watached(section, plexTo, user)
                except Exception as e:
                    if str(e).startswith('Unknown'):
                        print('Library ({}) does not have a watch status.'.format(library))
                    elif str(e).startswith('Invalid'):
                        print('Library ({}) not shared to user: {}.'.format(library, opts.userFrom))
                    elif str(e).startswith('(404)'):
                        print('Library ({}) not shared to user: {}.'.format(library, user))
                    else:
                        print(e)
                    pass
        # Check rating key from Tautulli
        elif opts.ratingKey:
            item = plexTo.fetchItem(opts.ratingKey)
            title = item.title.encode('utf-8')
            print('Syncing watch status of {} to {}\'s account.'.format(title, user))
            item.markWatched()
        else:
            print('No libraries or rating key provided.')
