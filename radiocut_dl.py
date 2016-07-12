"""Radiocut.fm downloader

Usage:
  radiocut-dl <radio-show-name> [-d <radio-show-date>] [-o <output-directory>]
  radiocut-dl -h | --help
  radiocut-dl --version

Options:
  -h --help     Show this screen.
  -v --version  Show version.
"""

from BeautifulSoup import BeautifulSoup
from datetime import datetime
from datetime import timedelta
from docopt import docopt
import shutil
import subprocess
import os
import time
import json
import logging
import urllib2
import sys

base_url = 'http://radiocut.fm'
radiocut_date_pattern = '%Y-%m-%d'
radiocut_datetime_pattern = '%Y-%m-%dT%H:%M:%S'
mp3_extension = '.mp3'
mp3_wrap_command = 'mp3wrap.exe'

__version__ = '0.0.1'

def setup_logging():
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    root.addHandler(ch)


def fetch_url(url):
    """Fetches the content for a single URL

    :type url: str
    Args:
        url (string): The URL to fetch.

    Returns:
        data_stream: The page obtained from the URL.

    Raises:
        HTTPError: Error if the page is not found.

    """
    opener = urllib2.build_opener()
    opener.addheaders = [('User-agent', 'Mozilla/5.0')]
    logging.debug('Retrieving URL: ' + url)
    try:
        result = opener.open(url).read()
    except urllib2.HTTPError, e:
        if '404' == str(e.code):
            logging.error('URL not found')
        raise
    logging.debug('URL retrieved')
    return result


def fetch_show_information(radio_show_name, radio_show_date = None):
    """Fetches the Radiocut radio show information

    Args:
        radio_show_name (string): Name of the Radiocut radio show
        radio_show_date (datetime): Date of the airing of the Radiocut radio show

    Returns:
        show_information (dict): The Radiocut show information

    Raises:
        HTTPError: Error if the page is not found.

    """
    show_url = base_url + '/api/radioshows/' + radio_show_name + '/last_recordings/'

    # Calculate query date
    if radio_show_date is not None:
        radio_show_date_str = datetime.strftime(radio_show_date, radiocut_date_pattern)
        logging.debug('Include date in URL: ' + radio_show_date_str)
        from_date = datetime.strftime(radio_show_date + timedelta(days=1), radiocut_datetime_pattern)
        show_url += '?now=' + from_date

    shows_list_json = json.loads(fetch_url(show_url))

    if radio_show_date is not None:
        radio_show_date_str = datetime.strftime(radio_show_date, radiocut_date_pattern)
        show_information = next(show for show in shows_list_json if radio_show_date_str in show['start'])
    else:
        show_information = shows_list_json[0]

    return show_information


def radiocutdate_to_datetime(radiocut_datetime_str):
    """Converts a Radiocut datetime string to a datetime

    Args:
        radiocut_datetime_str (string): Radiocut datetime string

    Returns:
        radiocut_datetime (datetime): Radiocut datetime
    """
    logging.debug('Datetime to convert: ' + radiocut_datetime_str)
    radiocut_datetime_str = radiocut_datetime_str[:-6]
    radiocut_datetime = datetime.strptime(radiocut_datetime_str, radiocut_datetime_pattern)
    return radiocut_datetime


def radiocutdate_to_epoch(radiocut_datetime_str):
    """Converts a Radiocut datetime string to epoch integer

    Args:
        radiocut_datetime_str (string): Radiocut datetime string

    Returns:
        radiocut_epoch (int): Radiocut epoch integer
    """
    logging.debug('Datetime to convert: ' + radiocut_datetime_str)
    radiocut_datetime_str = radiocut_datetime_str[:-6]
    radiocut_epoch = int(time.mktime(time.strptime(radiocut_datetime_str, radiocut_datetime_pattern)))
    logging.debug('Epoch converted: ' + str(radiocut_epoch))
    return radiocut_epoch


def epoch_to_radiocut_datetime_str(radiocut_epoch):
    """Converts an epoch integer to a Radiocut datetime string

    Args:
        radiocut_epoch (int): Radiocut epoch integer

    Returns:
        radiocut_epoch (string): Radiocut datetime string
    """
    logging.debug('Epoch to convert: ' + str(radiocut_epoch))
    radiocut_datetime = datetime.fromtimestamp(radiocut_epoch)
    logging.debug('Datetime converted: ' + radiocut_datetime.strftime(radiocut_datetime_pattern))
    return radiocut_datetime


def get_show_audio_info(show_info):
    """Retrieves the Radiocut show audio information given the show information

    Args:
        show_info (dict): Radiocut show information

    Returns:
        audio_info (dict): Radiocut audio information
    """
    logging.debug('Fetch audio info')
    show_url = base_url + show_info['url']
    page = fetch_url(show_url)
    soup = BeautifulSoup(page)
    result = soup.findAll('ul', {'class': 'audio_info'})
    audio_info = {'audio_station': result[0].findAll('li', {'class': 'audio_station'})[0].text,
                  'audio_seconds': result[0].findAll('li', {'class': 'audio_seconds'})[0].text,
                  'audio_duration': result[0].findAll('li', {'class': 'audio_duration'})[0].text,
                  'audio_base_url': result[0].findAll('li', {'class': 'audio_base_url'})[0].text,
                  'has_recordings_url': result[0].findAll('li', {'class': 'has_recordings_url'})[0].text,
                  'audio_time': result[0].findAll('li', {'class': 'audio_time'})[0].text}
    logging.debug('Audio info obtained')
    return audio_info


def fetch_json_chunks(audio_info, start_datetime, end_datetime):
    """Retrieve a list of all mp3 chunks that compose the Radiocut radio show provided the audio information
    start date and end date

    Args:
        audio_info (dict): Radiocut audio information
        start_datetime (datetime): Radiocut radio show start datetime
        end_datetime (datetime): Radiocut radio show end datetime

    Returns:
        radio_show_chunks_list (dict): Radiocut radio show chunks list
    """
    logging.debug('Fetch json chunks from audio info and start/end datetime')
    epoch_header = audio_info['audio_seconds']
    epoch_header = int(float(epoch_header[:6]))
    last_chunk_retrieved = False

    radio_show_chunks_list = []
    start_date_chunk = None

    while not last_chunk_retrieved:
        json_chunks_url = audio_info['audio_base_url'] + 'server/get_chunks/' + \
                          audio_info['audio_station'] + '/' + str(epoch_header) + '/'
        json_chunks = json.loads(fetch_url(json_chunks_url))
        for chunk in json_chunks[str(epoch_header)]['chunks']:
            start_date_chunk = epoch_to_radiocut_datetime_str(chunk['start'])
            if start_date_chunk > end_datetime:
                last_chunk_retrieved = True
                break
            if (start_date_chunk >= start_datetime) or (abs(start_datetime - start_date_chunk).seconds < 120):
                radio_show_chunks_list.append({'start': chunk['start'],
                               'url': json_chunks[str(epoch_header)]['baseURL'] + '/' + chunk['filename']
                               })
        if start_date_chunk < end_datetime:
            epoch_header += 1

    logging.debug('List of all chunks retrieved')
    return radio_show_chunks_list


def download_json_chunks(radio_show_name, mp3_chunks_list):
    """Download all mp3 chunks from a list for a Radiocut radio show

    Args:
        radio_show_name (str): Radiocut radio show name
        mp3_chunks_list (dict): Radiocut radio show chunks list

    Returns:
        radio_show_directory (str): Directory where all mp3 chunks have been saved
    """
    logging.debug('Retrieve each MP3 chunk')
    radio_show_date = epoch_to_radiocut_datetime_str(mp3_chunks_list[0]['start']).strftime(radiocut_date_pattern)
    radio_show_directory = radio_show_name + '-' + radio_show_date
    try:
        os.stat(radio_show_directory)
    except:
        os.mkdir(radio_show_directory)

    for chunk in mp3_chunks_list:
        mp3_stream = fetch_url(chunk['url'])
        with open(radio_show_directory + '/' + str(int(chunk['start'])) + mp3_extension, 'wb') as file_:
            file_.write(mp3_stream)

    logging.debug('All MP3 chunks retrieved and saved to ' + radio_show_directory)
    return radio_show_directory


def concatenate_mp3_chunks(radio_show_directory):
    """Concatenate all mp3 chunks into a single mp3 file

    Args:
        radio_show_directory (str): Directory where all mp3 chunks are for a radio show

    Returns:
        final_mp3_file (str): Filename for the resulting mp3 file
    """
    logging.debug('Create a single MP3 file for the radio show')
    expand_all_mp3_files = radio_show_directory + '/*' + mp3_extension
    final_mp3_file = radio_show_directory + mp3_extension

    subprocess.call([mp3_wrap_command, final_mp3_file, expand_all_mp3_files])

    shutil.move(radio_show_directory + '_MP3WRAP' + mp3_extension, final_mp3_file)
    shutil.rmtree(radio_show_directory)

    logging.debug('Radio show created: ' + final_mp3_file)
    return final_mp3_file

def radiocut_show_download(radio_show_name, radio_sho_date = None, output_directory = None):
    return None

def main():
    arguments = docopt(__doc__, version=__version__)
    radiocut_show_download(arguments['<radio-show-name>'], arguments['<radio-show-date>'], arguments['<output-directory>'])

if __name__ == '__main__':
    setup_logging()
    main()