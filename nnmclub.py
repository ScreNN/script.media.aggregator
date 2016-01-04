﻿# -*- coding: utf-8 -*-

import os, re
from settings import Settings
from base import *
from nfowriter import *
from strmwriter import *
import requests, time


_RSS_URL = 'http://nnm-club.me/forum/rss-topic.xml'
_BASE_URL = 'http://nnm-club.me/forum/'
_HD_PORTAL_URL = _BASE_URL + 'portal.php?c=11'

MULTHD_URL = 'http://nnm-club.me/forum/viewforum.php?f=661'

_NEXT_PAGE_SUFFIX='&start='

class DescriptionParser(DescriptionParserBase):
	
	def __init__(self, content, settings = None, tracker = False):
		Informer.__init__(self)
		
		self._dict.clear()
		self.content = content
		self.tracker = tracker
		self.settings = settings
		self.OK = self.parse()
		
	def get_tag(self, x):
		return {
			#u'Название:': u'title',
			#u'Оригинальное название:': u'originaltitle',
			#u'Год выхода:': u'year',
			u'Жанр:': u'genre',
			u'Режиссер:': u'director',
			u'Актеры:': u'actor',
			u'Описание:': u'plot',
			u'Продолжительность:': u'runtime',
			u'Качество видео:': u'format',
			u'Производство:' : u'country_studio',
			u'Видео:': u'video',
		}.get(x.strip(), u'')
		
	def clean(self, title):
		return title.strip(' \t\n\r')
		
	def get_title(self, full_title):
		try:
			sep = '/'
			if not ' / ' in full_title:
				sep = '\('
				
			found = re.search('^(.+?) ' + sep, full_title).group(1)
			return self.clean( found)
		except AttributeError:
			return full_title
	
	def get_original_title(self, full_title):
		if not ' / ' in full_title:
			return self.get_title(full_title)
			
		try:
			found = re.search('^.+? / (.+) \(', full_title).group(1)
			return self.clean(found)
		except AttributeError:
			return full_title
			
	def get_year(self, full_title):
		try:
			found = re.search('\(([0-9]+)\)', full_title).group(1)
			return unicode(found)
		except AttributeError:
			return 0
			
	def parse(self):
		a = None
		if self.tracker:
			a = self.content
		else:
			for __a in self.content.select('.substr a.pgenmed'):
				a = __a
				break
				
		if a != None:
			try:
				self.__link = _BASE_URL + a['href']
				print self.__link
			except:
				#print a.__repr__()
				return False

			full_title = a.get_text().strip(' \t\n\r')
			print 'full_title: ' + full_title.encode('utf-8')
						
			self._dict['full_title'] = full_title
			self._dict['title'] = self.get_title(full_title)
			self._dict['originaltitle'] = self.get_original_title(full_title)
			self._dict['year'] = self.get_year(full_title)
			
			if self.need_skipped(full_title):
				return False
			
			fname = make_fullpath(self.make_filename(), '.strm')
			if STRMWriterBase.has_link(fname, self.__link):
				print 'Already exists'
				return False
			
			r = requests.get(self.__link)
			if r.status_code == requests.codes.ok:
				self.soup = BeautifulSoup(clean_html(r.text), 'html.parser')
				
				tag = u''
				self._dict['gold'] = False
				for a in self.soup.select('img[src="images/gold.gif"]'):
					self._dict['gold'] = True
					print 'gold'
				
				for span in self.soup.select('span.postbody span'):
					try:
						text = span.get_text()
						tag = self.get_tag(text)
						if tag != '':
							if tag != u'plot':
								self._dict[tag] = unicode(span.next_sibling).strip()
							else:
								self._dict[tag] = unicode(span.next_sibling.next_sibling).strip()
							print '%s (%s): %s' % (text.encode('utf-8'), tag.encode('utf-8'), self._dict[tag].encode('utf-8'))
					except: pass
				if 'genre' in self._dict:
					self._dict['genre'] = self._dict['genre'].lower()

				count_id = 0
				for a in self.soup.select('#imdb_id'):
					try:
						href = a['href']
						components = href.split('/')
						if components[2] == u'www.imdb.com' and components[3] == u'title':
							self._dict['imdb_id'] = components[4]
							count_id += 1
					except:
						pass
						
				if count_id > 1:
					return False

				for img in self.soup.select('img.postImg'):
					try:
						self._dict['thumbnail'] = img['src']
						print self._dict['thumbnail']
					except:
						pass
				
				if 'country_studio' in self._dict:
					parse_string = self._dict['country_studio']
					parts = parse_string.split(' / ')
					self._dict['country'] = parts[0]
					if len(parts) > 1:
						self._dict['studio'] = parts[1]

				if self.settings:
					if self.settings.use_kinopoisk:
						for kp_id in self.soup.select('#kp_id'):
							self._dict['kp_id'] = kp_id['href']
							
				self.make_movie_api(self.get_value('imdb_id'), self.get_value('kp_id'))
				
				return True
		return False
		
	def link(self):
		return self.__link


class PostsEnumerator(object):		
	#==============================================================================================
	_items = []
	
	def __init__(self):
		self._s = requests.Session()

	def process_page(self, url):
		request = self._s.get(url)
		self.soup = BeautifulSoup(clean_html(request.text), 'html.parser')
		print url
		
		for tbl in self.soup.select('table.pline'):
			self._items.append(tbl)
		
	def items(self):
		return self._items
		
class TrackerPostsEnumerator(PostsEnumerator):
	def process_page(self, url):
		request = self._s.get(url)
		self.soup = BeautifulSoup(clean_html(request.text), 'html.parser')
		print url
		
		for a in self.soup.select('a.topictitle'):
			self._items.append(a)
		
def write_movie(post, settings, tracker):
	print '!-------------------------------------------'
	parser = DescriptionParser(post, settings = settings, tracker = tracker)
	if parser.parsed():
		print '+-------------------------------------------'
		full_title = parser.get_value('full_title')
		filename = parser.make_filename()
		if filename:
			print 'full_title: ' + full_title.encode('utf-8')
			print 'filename: ' + filename.encode('utf-8')
			print '-------------------------------------------+'
			STRMWriter(parser.link()).write(filename, rank = get_rank(parser.get_value('full_title'), parser, settings), settings = settings)
			NFOWriter().write(parser, filename)
			
			#time.sleep(1)

	del parser

def write_movies(content, path, settings, tracker = False):
	
	original_dir = filesystem.getcwd()
	
	if not filesystem.exists(path):
		filesystem.makedirs(path)
		
	filesystem.chdir(path)
	# ---------------------------------------------
	if tracker:
		_ITEMS_ON_PAGE = 50
		enumerator = TrackerPostsEnumerator()
	else:
		_ITEMS_ON_PAGE = 15
		enumerator = PostsEnumerator()
	for i in range(settings.nnmclub_pages):
		enumerator.process_page(content + _NEXT_PAGE_SUFFIX + str(i * _ITEMS_ON_PAGE))

	for post in enumerator.items():
		write_movie(post, settings, tracker)
	# ---------------------------------------------
	filesystem.chdir(original_dir)


def run(settings):
	write_movies(_HD_PORTAL_URL, settings.movies_path(), settings)
	write_movies(MULTHD_URL, settings.animation_path(), settings, tracker = True)
	#write_movies(_BASE_URL + 'portal.php?c=13', filesystem.join(settings.base_path(), u'Наши'), settings)
	
def get_magnet_link(url):
	r = requests.get(url)
	if r.status_code == requests.codes.ok:
		soup = BeautifulSoup(clean_html(r.text), 'html.parser')
		for a in soup.select('a[href*="magnet:"]'):
			print a['href']
			return a['href']
	return None
	
def download_torrent(url, path, settings):
	url = urllib2.unquote(url)
	print 'download_torrent:' + url
	s = requests.Session()
	
	r = s.get("http://nnm-club.me/forum/login.php")
	#with filesystem.fopen('log-get.html', 'w+') as f:
	#	f.write(r.text.encode('cp1251'))
	
	soup = BeautifulSoup(clean_html(r.text), 'html.parser')
	
	for inp in soup.select('input[name="code"]'):
		code = inp['value']
		print code
	
	data = {"username": settings.nnmclub_login, "password": settings.nnmclub_password, 
																"autologin": "on", "code": code, "redirect": "", "login": "" }
	login = s.post("http://nnm-club.me/forum/login.php", data = data, headers={'Referer': "http://nnm-club.me/forum/login.php"})
	#with filesystem.fopen('log-post.html', 'w+') as f:
	#	f.write(login.text.encode('cp1251'))
		
	#print login.headers
	print 'Login status: %d' % login.status_code
	
	#print login.text.encode('cp1251')
	
	page = s.get(url)
	#print page.text.encode('cp1251')
	
	soup = BeautifulSoup(clean_html(page.text), 'html.parser')
	a = soup.select('td.gensmall > span.genmed > b > a')
	if len(a) > 0:
		href = 'http://nnm-club.me/forum/' + a[0]['href']
		print s.headers
		r = s.get(href, headers={'Referer': url})
		print r.headers
		
		# 'Content-Type': 'application/x-bittorrent'
		if 'Content-Type' in r.headers:
			if not 'torrent' in r.headers['Content-Type']:
				return False
		
		try:
			with filesystem.fopen(path, 'wb') as torr:
				for chunk in r.iter_content(100000):
					torr.write(chunk)
			return True
		except: 
			pass

	return False
	

if __name__ == '__main__':
	settings = Settings('../../..', nnmclub_pages = 2)
	run(settings)
	
