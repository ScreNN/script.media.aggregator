﻿# coding: utf-8

import log
from log import debug, print_tb


import feedparser, filesystem
import xml.etree.cElementTree as ET
from bs4 import BeautifulSoup
import urllib2
import json, os
from settings import Settings
from base import *
from movieapi import *
from nfowriter import *
from strmwriter import *

class DescriptionParser(DescriptionParserBase):

	def __init__(self, full_title, content, link, settings):
		self._link = link
		DescriptionParserBase.__init__(self, full_title, content, settings)

	def link(self):
		return self._link

	def get_tag(self, x):
		return {
			u'Название:': u'title',
			u'Оригинальное название:': u'originaltitle',
			u'Год выхода:': u'year',
			u'Жанр:': u'genre',
			u'Режиссер:': u'director',
			u'В ролях:': u'actor',
			u'Сюжет фильма:': u'plot',
			u'Продолжительность:': u'runtime',
			u'Формат:': u'format',
			u'Видео:': u'video',
			u'Выпущено:': u'country_studio'
		}.get(x, u'')
		
	def parse(self):
		#title - Название:
		tag = u''
		self._dict['gold'] = False
		for span in self.soup.select('span'):
			try:
				text = span.get_text()
				if text == u'BDInfo Report':
					return False
				
				if text == u'Золотая раздача':
					self._dict['gold'] = True
				
				#debug(text.encode('utf-8'))
				if tag == u'':
					tag = self.get_tag(text.strip(' \t\n\r'))
				else:
					self._dict[tag] = text.strip(' \t\n\r')
					tag = u''
			except:
				pass

		self.parse_country_studio()

		count_id = 0
		for a in self.soup.select('a'):
			try:
				href = a['href']
				components = href.split('/')
				if components[2] == u'www.imdb.com' and components[3] == u'title':
					self._dict['imdb_id'] = components[4]
					count_id += 1
				
				if self.settings:
					if self.settings.use_kinopoisk and components[2] == u'www.kinopoisk.ru':
						self._dict['kp_id'] = href

			except:
				pass
				
		if count_id > 1:
			return False
				
		for img in self.soup.select('img[src*="thumbnail.php"]'):
			try:
				self._dict['thumbnail'] = img['src']
				debug(self._dict['thumbnail'])
			except:
				pass

		self.make_movie_api(self.get_value('imdb_id'), self.get_value('kp_id'))
				
		return True
		
def write_movie(item, settings):
	full_title = item.title
	debug('full_title: ' + full_title.encode('utf-8'))

	parser = DescriptionParser(full_title, item.description, item.link,	settings)
	debug('-------------------------------------------------------------------------')
	
	if parser.need_skipped(full_title):
		return
	
	if parser.parsed():
		filename = parser.make_filename()
		if not filename:
			return
		
		debug('filename: ' + filename.encode('utf-8'))
		STRMWriter(item.link).write(filename, parser=parser, settings=settings)
		NFOWriter(parser, movie_api=parser.movie_api()).write_movie(filename)
		from downloader import TorrentDownloader
		TorrentDownloader(item.link, settings.torrents_path(), settings).download()
	else:
		skipped(item)
		
	del parser
		
def write_movies(rss_url, path, settings):
	with filesystem.save_make_chdir_context(path):
		d = feedparser.parse(rss_url)

		cnt = 0
		settings.progress_dialog.update(0, 'hdclub', path)

		for item in d.entries:
			write_movie(item, settings)

			cnt += 1
			settings.progress_dialog.update(cnt * 100 / len(d.entries), 'hdclub', path)


def write_tvshow(item, settings):
	full_title = item.title
	debug('full_title: ' + full_title.encode('utf-8'))

	parser = DescriptionParser(full_title, item.description, item.link, settings)
	debug('-------------------------------------------------------------------------')

	if parser.need_skipped(full_title):
		return

	if parser.parsed():
		import tvshowapi
		tvshowapi.write_tvshow(full_title, item.link, settings, parser)

	del parser

def write_tvshows(rss_url, path, settings):

	with filesystem.save_make_chdir_context(path):
		d = feedparser.parse(rss_url)

		cnt = 0
		settings.progress_dialog.update(0, 'hdclub', path)

		for item in d.entries:
			write_tvshow(item, settings)

			cnt += 1
			settings.progress_dialog.update(cnt * 100 / len(d.entries), 'hdclub', path)


def get_rss_url(f_id, passkey):
	return 'http://hdclub.org/rss.php?cat=' + str(f_id) + '&passkey=' + passkey


def run(settings):
	if settings.animation_save:
		write_movies(settings.animation_url, settings.animation_path(), settings)

	if settings.documentary_save:
		write_movies(settings.documentary_url, settings.documentary_path(), settings)

	if settings.movies_save:
		write_movies(settings.movies_url, settings.movies_path(), settings)

	if settings.tvshows_save:
		write_tvshows(get_rss_url(64, settings.hdclub_passkey), settings.tvshow_path(), settings)


def make_search_url(what, IDs, imdb, settings):
	url = u'http://hdclub.org/browse.php'   # ?c71=1&webdl=0&3d=0&search=%D2%EE%F0&incldead=0&dsearch=&stype=or'
	url += '?c=' + str(IDs)
	url += '&passkey=' + settings.hdclub_passkey
	url += '&search=' + urllib2.quote(what.encode('utf-8'))
	url += '&dsearch=' + imdb
	return url


def search_generate(what, imdb, settings):

	count = 0

	session = requests.session()

	if settings.movies_save:
		url = make_search_url(what, 71, imdb, settings)
		result1 = search_results(imdb, session, settings, url, 71)
		with filesystem.save_make_chdir_context(settings.movies_path()):
			count += make_search_strms(result1, settings, 'movie')

	if settings.animation_save:
		url = make_search_url(what, 70, imdb, settings)
		result2 = search_results(imdb, session, settings, url, 70)
		with filesystem.save_make_chdir_context(settings.animation_path()):
			count += make_search_strms(result2, settings, 'movie')

	if settings.documentary_save:
		url = make_search_url(what, 78, imdb, settings)
		result3 = search_results(imdb, session, settings, url, 78)
		with filesystem.save_make_chdir_context(settings.documentary_path()):
			count += make_search_strms(result3, settings, 'movie')

	if settings.tvshows_save:
		url = make_search_url(what, 64, imdb, settings)
		result4 = search_results(imdb, session, settings, url, 64)
		with filesystem.save_make_chdir_context(settings.tvshow_path()):
			count += make_search_strms(result4, settings, 'tvshow')

	return count


def make_search_strms(result, settings, type):
	count = 0
	for item in result:
		link = item['link']
		parser = item['parser']
		if link:
			if type == 'movie':
				import movieapi
				movieapi.write_movie(parser.get_value('full_title'), link, settings, parser)
				count += 1
			if type == 'tvshow':
				import tvshowapi
				tvshowapi.write_tvshow(parser.get_value('full_title'), link, settings, parser)
				count += 1

	return count


class TrackerPostsEnumerator(object):
	_items = []

	def __init__(self, session):
		self._s = session
		self._items[:] = []

	def items(self):
		return self._items

	def process_page(self, url):
		request = self._s.get(url)
		self.soup = BeautifulSoup(clean_html(request.text), 'html.parser')
		debug(url)

		# item = {}
		# item['category'] = cat_a['href']
		# item['a'] = topic_a
		# item['dl_link'] = dl_a['href']
		# item['seeds'] = seeds_td.get_text()
		# self._items.append(item.copy())

		tbody = self.soup.find('tbody', attrs={'id': 'highlighted'})
		if tbody:
			for tr in tbody:
				try:
					from bs4 import NavigableString
					if isinstance(tr, NavigableString):
						continue

					item = {}
					TDs = tr.find_all('td', recursive=False)
					item['a'] = TDs[2].find('a')['href']
					item['title'] = TDs[2].find('a').get_text().strip(' \n\r\t')
					item['dl_link'] = item['a'].replace('details.php', 'download.php')
					item['seeds'] = TDs[4].get_text().strip(' \n\r\t')
					item['cat'] = TDs[0].find('a')['href'].split('cat=')[-1]
					self._items.append(item.copy())
				except BaseException as e:
					log.print_tb(e)

def search_results(imdb, session, settings, url, cat):
	debug('search_results: url = ' + url)

	enumerator = TrackerPostsEnumerator(session)
	enumerator.process_page(url)
	result = []
	for post in enumerator.items():
		if 'seeds' in post and int(post['seeds']) < 5:
			continue

		if str(post.get('cat', '')) != str(cat):
			continue

		# full_title, content, link, settings

		page = requests.get('http://hdclub.org/' + post['a'])

		soup = BeautifulSoup(page.text)

		content = ''
		tbl = soup.find('table', class_='heading_b')

		for td in tbl.find_all('td', class_='heading_r'):
			content += td.prettify()

		with filesystem.fopen('hdclub.' + imdb + '.html', 'w') as html:
			html.write(content.encode('utf-8'))

		parser = DescriptionParser(post['title'], content, post['a'], settings=settings)
		debug(u'%s %s %s' % (post['title'], str(parser.parsed()), parser.get_value('imdb_id')))
		if parser.parsed(): # and parser.get_value('imdb_id') == imdb:
			result.append({'parser': parser, 'link': post['dl_link']})

	return result


def download_torrent(url, path, settings):
	url = url.replace('details.php', 'download.php')
	if not 'passkey' in url:
		url += '&passkey=' + settings.hdclub_passkey

	try:
		import shutil
		response = urllib2.urlopen(url)
		with filesystem.fopen(path, 'wb') as f:
			shutil.copyfileobj(response, f)
		return True
	except BaseException as e:
		print_tb(e)
		return False


