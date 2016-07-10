from BeautifulSoup import BeautifulSoup
from datetime import datetime
from datetime import timedelta
import shutil
import subprocess
import os
import time
import json
import logging
import urllib2
import sys

base_url = 'http://radiocut.fm'
radiocut_date_pattern = '%Y-%m-%dT%H:%M:%S'


def setup_logging():
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    root.addHandler(ch)


def fetch_url(url):
    opener = urllib2.build_opener()
    opener.addheaders = [('User-agent', 'Mozilla/5.0')]
    try:
        logging.info('Retrieving URL: ' + url)
        result = opener.open(url).read()
    except urllib2.HTTPError, e:
        if '404' == str(e.code):
            logging.error('Radio show not found')
        raise
    logging.info('URL retrieved')
    return result


def fetch_show_information(radio_show_name, radio_show_date = None):
    show_url = base_url + '/api/radioshows/' + radio_show_name + '/last_recordings/'

    # Calculate query date
    if radio_show_date is not None:
        radio_show_date_str = datetime.strftime(radio_show_date, '%Y-%m-%dT')
        from_date = datetime.strftime(radio_show_date + timedelta(days=1), radiocut_date_pattern)
        # Modify URL to fetch show for specified date
        show_url += '?now=' + from_date
        shows_list_json = json.loads(fetch_url(show_url))
        result = next(show for show in shows_list_json if radio_show_date_str in show['start'])
    else:
        shows_list_json = json.loads(fetch_url(show_url))
        result = shows_list_json[0]

    return result


def radiocutdate_to_datetime(radiocutdate):
    logging.info('Datetime to convert: ' + radiocutdate)
    radiocutdate = radiocutdate[:-6]
    dt = datetime.strptime(radiocutdate, radiocut_date_pattern)
    return dt


def radiocutdate_to_epoch(radiocutdate):
    logging.info('Datetime to convert: ' + radiocutdate)
    radiocutdate = radiocutdate[:-6]
    epoch = int(time.mktime(time.strptime(radiocutdate, radiocut_date_pattern)))
    logging.info('Epoch converted: ' + str(epoch))
    return epoch


def epoch_to_date(epoch):
    logging.info('Epoch to convert: ' + str(epoch))
    converted_datetime = datetime.fromtimestamp(epoch)
    logging.info('Datetime converted: ' + converted_datetime.strftime(radiocut_date_pattern))
    return converted_datetime


def get_show_audio_info(show_info):
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
    return audio_info


def fetch_json_chunks(audio_info, start_datetime, end_datetime):
    epoch_header = audio_info['audio_seconds']
    epoch_header = int(float(epoch_header[:6]))
    last_chunk_retrieved = False

    chunks = []
    start_date_chunk = None

    while not last_chunk_retrieved:
        json_chunks_url = audio_info['audio_base_url'] + 'server/get_chunks/' + \
                          audio_info['audio_station'] + '/' + str(epoch_header) + '/'
        json_chunks = json.loads(fetch_url(json_chunks_url))
        for chunk in json_chunks[str(epoch_header)]['chunks']:
            start_date_chunk = epoch_to_date(chunk['start'])
            if start_date_chunk > end_datetime:
                last_chunk_retrieved = True
                break
            if (start_date_chunk >= start_datetime) or (abs(start_datetime - start_date_chunk).seconds < 120):
                chunks.append({'start': chunk['start'],
                               'url': json_chunks[str(epoch_header)]['baseURL'] + '/' + chunk['filename']
                               })
        if start_date_chunk < end_datetime:
            epoch_header += 1

    return chunks


def download_json_chunks(radio_show_name, mp3_chunks_list):
    radio_show_date = epoch_to_date(mp3_chunks_list[0]['start']).strftime('%Y-%m-%d')
    radio_show_directory = radio_show_name + '-' + radio_show_date
    try:
        os.stat(radio_show_directory)
    except:
        os.mkdir(radio_show_directory)

    for chunk in mp3_chunks_list:
        mp3_stream = fetch_url(chunk['url'])
        with open(radio_show_directory + '/' + str(int(chunk['start'])) + '.mp3', 'wb') as file_:
            file_.write(mp3_stream)

    return radio_show_directory


def concatenate_mp3_chunks(radio_show_directory):
    expand_all_mp3_files = radio_show_directory + '/*.mp3'
    final_mp3_file = radio_show_directory + '.mp3'

    subprocess.call(['mp3wrap.exe', final_mp3_file, expand_all_mp3_files])

    shutil.move(radio_show_directory + '_MP3WRAP.mp3', final_mp3_file)
    shutil.rmtree(radio_show_directory)

    return radio_show_directory + '.mp3'

#setup_logging()
