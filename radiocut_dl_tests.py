from datetime import datetime
import os
import unittest
import urllib2
import radiocut_dl
import logging


class RadiocutShowDownloadFunctions(unittest.TestCase):
    def setUp(self):
        self.radio_show_name = 'marca-de-radio'
        self.radio_show_output_filename = 'marca-de-radio-2016-07-09'
        self.radiocut_sample_date = datetime.strptime('2016-07-09T10:00:00', '%Y-%m-%dT%H:%M:%S')
        self.radiocut_sample_date_str = '2016-07-09T10:00:00-03:00'
        self.radiocut_sample_date_as_epoch = 1468069200

        self.specific_datetime = datetime.strptime('2016-07-02', '%Y-%m-%d')
        self.specific_datetime_nonexistent = datetime.strptime('2016-07-03', '%Y-%m-%d')
        self.show_info_specific_datetime = {'radio': 'La Red',
                          'start': '2016-07-02T10:00:00-03:00',
                          'end': '2016-07-02T13:00:00-03:00',
                          'url': '/radiostation/lared/listen/2016/07/02/10/00/00/'}

        self.show_info = {'radio': 'La Red',
                          'start': '2016-07-09T10:00:00-03:00',
                          'end': '2016-07-09T13:00:00-03:00',
                          'url': '/radiostation/lared/listen/2016/07/09/10/00/00/'}
        self.audio_info = {'audio_station': 'lared',
                           'audio_base_url': 'http://chunkserver.radiocut.fm/',
                           'audio_seconds': '1468069200',
                           'has_recordings_url': '/radiostation/lared/has_recordings_at/1468069200'}

        logging.info('----------------')
        logging.info('TEST BEGINS')

    def tearDown(self):
        self.audio_info = {}
        logging.info('TEST COMPLETE')
        logging.info('----------------')

    def test_should_fetch_marca_de_radio_show_info(self):
        logging.info('Fetch show info')
        show_info = radiocut_dl.fetch_show_information(self.radio_show_name)
        self.assertEqual(show_info['radio'], self.show_info['radio'])
        self.assertEqual(show_info['start'], self.show_info['start'])
        self.assertEqual(show_info['end'], self.show_info['end'])
        self.assertEqual(show_info['url'], self.show_info['url'])

    def test_should_fetch_show_information_on_specific_date(self):
        logging.info('Fetch show info for a specific date')
        show_info = radiocut_dl.fetch_show_information(self.radio_show_name, self.specific_datetime)
        self.assertEqual(show_info['radio'], self.show_info_specific_datetime['radio'])
        self.assertEqual(show_info['start'], self.show_info_specific_datetime['start'])
        self.assertEqual(show_info['end'], self.show_info_specific_datetime['end'])
        self.assertEqual(show_info['url'], self.show_info_specific_datetime['url'])

    def test_should_fail_to_fetch_show_information_on_date(self):
        logging.info('Should fail to fetch show information on a date where the show was not broadcasted')
        self.assertRaises(StopIteration, radiocut_dl.fetch_show_information, self.radio_show_name, self.specific_datetime_nonexistent)

    def test_should_fail_to_fetch_non_existent_show(self):
        logging.info('Fetch show info fails')
        self.assertRaises(urllib2.HTTPError, radiocut_dl.fetch_show_information, 'show-does-not-exist')

    def test_should_convert_date_string_to_epoch(self):
        logging.info('Convert date to epoch')
        epoch_date = radiocut_dl.radiocutdate_to_epoch(self.radiocut_sample_date_str)
        self.assertEquals(epoch_date, self.radiocut_sample_date_as_epoch)

    def test_should_convert_epoch_to_radiocutdate(self):
        logging.info('Convert epoch to Radiocut date')
        converted_datetime = radiocut_dl.epoch_to_radiocut_datetime_str(self.radiocut_sample_date_as_epoch)
        self.assertEquals(converted_datetime.strftime('%Y-%m-%dT%H:%M:%S'), self.radiocut_sample_date.strftime('%Y-%m-%dT%H:%M:%S'))

    def test_should_convert_radiocutdate_to_datetime(self):
        logging.info('Convert Radiocut date to datetime')

        converted_datetime = radiocut_dl.radiocutdate_to_datetime(self.radiocut_sample_date_str)
        self.assertEquals(converted_datetime.strftime('%Y-%m-%dT%H:%M:%S'), self.radiocut_sample_date.strftime('%Y-%m-%dT%H:%M:%S'))

    def test_should_get_audio_info(self):
        logging.info('Fetch show audio info')
        audio_info_result = radiocut_dl.fetch_show_audio_info(self.show_info)
        self.assertEquals(audio_info_result['audio_station'], self.audio_info['audio_station'])
        self.assertEquals(audio_info_result['audio_seconds'], self.audio_info['audio_seconds'])
        self.assertEquals(audio_info_result['audio_base_url'], self.audio_info['audio_base_url'])
        self.assertEquals(audio_info_result['has_recordings_url'], self.audio_info['has_recordings_url'])

    def test_should_get_json_chunks(self):
        logging.info('Fetch JSON chunks for a radio station and date')
        # Get the start and end epoch dates
        start_date = radiocut_dl.radiocutdate_to_datetime(self.show_info['start'])
        end_date = radiocut_dl.radiocutdate_to_datetime(self.show_info['end'])

        # Retrieve the mp3 chunks list
        mp3_chunks_list = radiocut_dl.fetch_json_chunks(self.audio_info, start_date, end_date)

        # Assert it's not an empty list
        self.assertTrue(len(mp3_chunks_list) > 0)

        # Convert the first and last chunks start epoch values to datetime
        first_chunk_start_date = radiocut_dl.epoch_to_radiocut_datetime_str(mp3_chunks_list[0]['start'])
        last_chunk_start_date = radiocut_dl.epoch_to_radiocut_datetime_str(mp3_chunks_list[-1]['start'])

        # Calculate the time length, as it should be less than 15 min apart for both
        delta_start_minutes = abs(first_chunk_start_date - start_date).seconds / 60
        delta_end_minutes = abs(last_chunk_start_date - end_date).seconds / 60

        self.assertTrue(delta_start_minutes < 15)
        self.assertTrue(delta_end_minutes < 15)

    def test_should_download_and_concat_all_mp3_chunks(self):
        logging.info('Fetch all MP3 chunks, download and concatenate into a single MP3 file')
        # Get the start and end epoch dates
        start_date = radiocut_dl.radiocutdate_to_datetime(self.show_info['start'])
        end_date = radiocut_dl.radiocutdate_to_datetime(self.show_info['end'])

        # Retrieve the mp3 chunks list
        mp3_chunks_list = radiocut_dl.fetch_json_chunks(self.audio_info, start_date, end_date)

        radio_show_directory = radiocut_dl.download_json_chunks(self.radio_show_name, mp3_chunks_list)

        self.assertTrue(os.stat(radio_show_directory) != None)
        self.assertEqual(len(os.listdir(radio_show_directory)), len(mp3_chunks_list))

        radio_show_mp3 = radiocut_dl.concatenate_mp3_chunks(radio_show_directory, self.radio_show_output_filename)

        self.assertTrue(os.stat(radio_show_mp3))
        os.remove(radio_show_mp3)

    #una vez bajado, si la conexion con dropbox esta disponible, subir el archivo
    #http://stackoverflow.com/questions/23894221/upload-file-to-my-dropbox-from-python-script
