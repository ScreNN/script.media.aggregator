﻿# -*- coding: utf-8 -*-

import log
from log import debug


import json, re, base
import urllib2, requests
from bs4 import BeautifulSoup

def write_movie(fulltitle, link, settings, parser):
	debug('+-------------------------------------------')
	filename = parser.make_filename()
	if filename:
		debug('fulltitle: ' + fulltitle.encode('utf-8'))
		debug('filename: ' + filename.encode('utf-8'))
		debug('-------------------------------------------+')
		from strmwriter import STRMWriter
		STRMWriter(parser.link()).write(filename,
										parser=parser,
										settings=settings)
		from nfowriter import NFOWriter
		NFOWriter(parser, movie_api = parser.movie_api()).write_movie(filename)

		from downloader import TorrentDownloader
		TorrentDownloader(parser.link(), settings.torrents_path(), settings).download()

def get_tmdb_api_key():
	try:
		import xbmc, filesystem
		xml_path = xbmc.translatePath('special://home').decode('utf-8')
		xml_path = filesystem.join(xml_path, 'addons/metadata.common.themoviedb.org/tmdb.xml')
		with filesystem.fopen(xml_path, 'r') as xml:
			content = xml.read()
			match = re.search('api_key=(\w+)', content)
			if match:
				key = match.group(1)
				debug('get_tmdb_api_key: ok')
				return key

	except BaseException as e:
		debug('get_tmdb_api_key: ' + str(e))
		return 'f7f51775877e0bb6703520952b3c7840'


class tmdb_movie_item(object):
	def __init__(self, json_data):
		self.json_data_ = json_data

	def poster(self):
		try:
			return 'http://image.tmdb.org/t/p/w500' + self.json_data_['poster_path']
		except BaseException:
			return ''

	def fanart(self):
		try:
			return 'http://image.tmdb.org/t/p/original' + self.json_data_['backdrop_path']
		except BaseException:
			return ''

	def get_art(self):
		art = {}

		path = self.poster()

		art['thumb'] = path
		art['poster'] = path
		art['thumbnailImage'] = path

		art['fanart'] = self.fanart()

		return art

	def get_info(self):
		info = {}

		if 'genres' in self.json_data_:
			info['genre'] = u', '.join([i['name'] for i in self.json_data_['genres']])

		analogy = {
			'aired': 'release_date',
			'plot': 'overview',
			'title': 'name',
			'originaltitle': 'originalname',
		}

		for tag in analogy:
			if analogy[tag] in self.json_data_:
				info[tag] = self.json_data_[analogy[tag]]

		if 'aired' in info:
			aired = info['aired']
			m = re.search('(\d\d\d\d)', aired)
			if m:
				info['year'] = int(m.group(1))

		try:
			vid_item = self.json_data_['videos']['results'][0]
			if vid_item['site'] == 'YouTube':
				info['trailer'] = 'plugin://plugin.video.youtube/?action=play_video&videoid=' + vid_item['key']
		except BaseException:
			pass

		string_items = ['director', 'mpaa', 'title', 'originaltitle', 'duration', 'studio', 'code', 'album', 'votes', 'thumb']
		for item in string_items:
			if item in self.json_data_:
				info[item] = self.json_data_[item]

		#  'credits',

		return info

	def imdb(self):
		try:
			if 'imdb_id' in self.json_data_:
				return self.json_data_['imdb_id']
			elif 'external_ids' in self.json_data_ and 'imdb_id' in self.json_data_['external_ids']:
				return self.json_data_['external_ids']['imdb_id']

		except BaseException:
			return None


	def tmdb_id(self):
		if 'id' in self.json_data_:
			return self.json_data_['id']
		else:
			return None


		#integer_items = ['year', 'episode', 'season', 'top250', 'tracknumber']

		#float_items = ['rating']


class KinopoiskAPI(object):
	def __init__(self, kinopoisk_url = None):
		self.kinopoisk_url = kinopoisk_url
		self.soup = None
		self.actors = []

	def getTitle(self):
		title = None
		if self.kinopoisk_url and self.soup is None:
			r = requests.get(self.kinopoisk_url)
			if r.status_code == requests.codes.ok:
				self.soup = BeautifulSoup(base.clean_html(r.text), 'html.parser')

		if self.soup:
			h = self.soup.find('h1', class_ = 'moviename-big')
			if h:
				title = h.contents[0].strip()

		return title

	def Actors(self):
		if len(self.actors) > 0:
			return self.actors

		if self.kinopoisk_url:
			cast_url = self.kinopoisk_url + 'cast/'
			r = requests.get(cast_url)
			if r.status_code == requests.codes.ok:
				soup = BeautifulSoup(base.clean_html(r.text), 'html.parser')
				for a in soup.select('a[name="actor"]'):
					for sibling in a.next_siblings:
						if not hasattr(sibling, 'tag'):
							continue
						if sibling.tag == 'a':
							return self.actors
						for actorInfo in sibling.select('.actorInfo'):
							photo 		= actorInfo.select('div.photo a')[0]['href']
							#http://st.kp.yandex.net/images/actor_iphone/iphone360_30098.jpg
							#/name/7627/
							photo 		= photo.replace('/', '').replace('name', '')
							photo 		= 'http://st.kp.yandex.net/images/actor_iphone/iphone360_' + photo + '.jpg'
							ru_name		= actorInfo.select('div.info .name a')[0].get_text()
							en_name		= actorInfo.select('div.info .name span')[0].get_text()
							role		= actorInfo.select('div.info .role')[0].get_text().replace('... ', '')
							role 		= role.split(',')[0]
							self.actors.append({'photo': photo,'ru_name': ru_name,'en_name': en_name,'role': role})
		return self.actors

	def __trailer(self, element):
		for parent in element.parents:
			#debug(parent.tag)
			if parent.name == 'tr':
				for tr in parent.next_siblings:
					if not hasattr(tr, 'select'):
						continue
					if tr.name != 'tr':
						continue
					for a_cont in tr.select('a.continue'):
						if u'Высокое качество' in a_cont.get_text():
							trailer = a_cont['href']
							trailer = re.search('link=(.+?)$', trailer).group(1)
							try:
								debug('trailer: ' + trailer)
							except:
								pass
							return trailer
		return None

	def Trailer(self):
		if self.kinopoisk_url:
			trailer_page = self.kinopoisk_url + 'video/type/1/'
			r = requests.get(trailer_page)
			if r.status_code == requests.codes.ok:
				soup = BeautifulSoup(base.clean_html(r.text), 'html.parser')
				for div in soup.select('tr td div div.flag2'):
					trailer = self.__trailer(div)
					if trailer:
						return trailer
				for a in soup.select('a.all'):
					return self.__trailer(a)
		return None

class MovieAPI(KinopoiskAPI):
	api_url		= 'https://api.themoviedb.org/3'
	tmdb_api_key = get_tmdb_api_key()

	@staticmethod
	def url_imdb_id(idmb_id, type='movie'):
		return 'http://api.themoviedb.org/3/' + type + '/' + idmb_id + '?api_key=' + MovieAPI.tmdb_api_key + '&language=ru'

	@staticmethod
	def search(title):
		url = 'http://api.themoviedb.org/3/search/movie?query=' + urllib2.quote(title.encode('utf-8')) + '&api_key=' + MovieAPI.tmdb_api_key + '&language=ru'
		movies = MovieAPI.tmdb_query(url)
		url = 'http://api.themoviedb.org/3/search/tv?query=' + urllib2.quote(title.encode('utf-8')) + '&api_key=' + MovieAPI.tmdb_api_key + '&language=ru'
		tv = MovieAPI.tmdb_query(url, 'tv')
		return movies + tv

	@staticmethod
	def tmdb_query(url, type='movie'):
		result = []
		try:
			data = json.load(urllib2.urlopen(url))
		except urllib2.HTTPError:
			return []


		for tag in ['results', 'movie_results', 'tv_results']:
			if tag in data:
				for r in data[tag]:
					if not r['overview']:
						continue

					url2 = 'http://api.themoviedb.org/3/' + type + '/' + str(
						r['id']) + '?api_key=' + MovieAPI.tmdb_api_key + '&language=ru&append_to_response=credits,videos,external_ids'
					data2 = json.load(urllib2.urlopen(url2))

					if 'imdb_id' in data2:
						result.append(tmdb_movie_item(data2))
					elif 'external_ids' in data2 and 'imdb_id' in data2['external_ids']:
						result.append(tmdb_movie_item(data2))

		return result

	@staticmethod
	def tmdb_by_imdb(imdb, type):
		url = 'http://api.themoviedb.org/3/find/' + imdb + '?external_source=imdb_id&api_key=' + MovieAPI.tmdb_api_key + '&language=ru'
		url += '&append_to_response=credits,videos,external_ids'
		debug(url)
		return MovieAPI.tmdb_query(url, type)

	@staticmethod
	def popular():
		url = 'http://api.themoviedb.org/3/movie/popular?api_key=' + MovieAPI.tmdb_api_key + '&language=ru'
		return MovieAPI.tmdb_query(url)

	@staticmethod
	def popular_tv():
		url = 'http://api.themoviedb.org/3/tv/popular?api_key=' + MovieAPI.tmdb_api_key + '&language=ru'
		return MovieAPI.tmdb_query(url, 'tv')

	@staticmethod
	def top_rated():
		url = 'http://api.themoviedb.org/3/movie/top_rated?api_key=' + MovieAPI.tmdb_api_key + '&language=ru'
		return MovieAPI.tmdb_query(url)

	@staticmethod
	def top_rated_tv():
		url = 'http://api.themoviedb.org/3/tv/top_rated?api_key=' + MovieAPI.tmdb_api_key + '&language=ru'
		return MovieAPI.tmdb_query(url, 'tv')

	@staticmethod
	def show_similar_t(tmdb_id, type):
		url = 'http://api.themoviedb.org/3/' + type + '/' + str(
				tmdb_id) + '/similar?api_key=' + MovieAPI.tmdb_api_key + '&language=ru'
		log.debug(url)
		return MovieAPI.tmdb_query(url, type)

	@staticmethod
	def show_similar(tmdb_id):
		return MovieAPI.show_similar_t(tmdb_id, 'movie') + MovieAPI.show_similar_t(tmdb_id, 'tv')

	def __init__(self, imdb_id = None, kinopoisk = None):
		KinopoiskAPI.__init__(self, kinopoisk)

		if imdb_id:
			url_ = MovieAPI.url_imdb_id(imdb_id)
			try:
				self.tmdb_data 	= json.load(urllib2.urlopen( url_ ))
				debug('tmdb_data (' + url_ + ') \t\t\t[Ok]')
			except:
				pass

			try:
				omdb_url = 'http://www.omdbapi.com/?i=' + imdb_id + '&plot=short&r=json'
				self.omdbapi	= json.load(urllib2.urlopen( omdb_url ))
				debug('omdbapi (' + omdb_url + ') \t\t\t[Ok]')
			except:
				pass
			

	def imdbRating(self):
		return self.omdbapi['imdbRating']
		
	def Runtime(self):
		return self.omdbapi['Runtime'].encode('utf-8').replace(' min', '')
		
	def Rated(self):
		return self.omdbapi.get(u'Rated', u'')

	def Poster(self):
		return self.omdbapi.get(u'Poster', u'')
		
	def Collection(self):                           
		try:
			if u'belongs_to_collection' in self.tmdb_data:
				belongs_to_collection = self.tmdb_data[u'belongs_to_collection']
				if u'name' in belongs_to_collection:
					return belongs_to_collection[u'name']
		except:
			pass
			
		return u''
		
	def Tags(self):
		tags = []
		try:
			if u'tagline' in self.tmdb_data:
				tagline = self.tmdb_data[u'tagline']
				for tag in tagline.split(','):
					tag = tag.strip()
					if len(tag) > 0:
						tags.append(tag)
		except:
			pass
			
		return tags

	def __getitem__(self, key):
		return self.tmdb_data[key]


if __name__ == '__main__':
	#for res in MovieAPI.search(u'паук'):
	#	print res.get_info()

	#for res in MovieAPI.popular_tv():
	#	print res.get_info()

	MovieAPI.tmdb_query(
		'http://api.themoviedb.org/3/movie/tt4589186?api_key=f7f51775877e0bb6703520952b3c7840&language=ru')