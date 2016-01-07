import xbmc, json, filesystem, xbmcvfs, os, re
import xml.etree.ElementTree as ET

import inspect
def lineno():
    """Returns the current line number in our program."""
    return inspect.currentframe().f_back.f_lineno

class AdvancedSettingsReader(object):
	dict = {}
	def LOG(self, s):
		print '[AdvancedSettingsReader]: ' + s
	
	def __init__(self):
		self.use_mysql = False
		self.dict.clear()
	
		path = xbmc.translatePath('special://profile/advancedsettings.xml').decode('utf-8')
		self.LOG(path)
		if not filesystem.exists(path):
			return

		try:
			with filesystem.fopen(path, 'r') as f:
				content = f.read()
				root = ET.fromstring(content)
		except IOError as e:
			self.LOG("I/O error({0}): {1}".format(e.errno, e.strerror))

		for section in root:
			if section.tag == 'videodatabase':
				for child in section:
					if child.tag in ['type', 'host', 'port', 'user', 'pass', 'name']:
						self.dict[child.tag] = child.text
						print child.text
				self.LOG('<videodatabase> found')
				return
				
		self.LOG('<videodatabase> not found')
		
	def __getitem__(self, key):
		return self.dict.get(key, None)

reader = AdvancedSettingsReader()
		
		
BASE_PATH = 'special://database'		
class VideoDatabase(object):
	@staticmethod
	def find_last_version(name):
		dirs, files = xbmcvfs.listdir(BASE_PATH)
		matched_files = [f for f in files if f.startswith(name)]
		versions = [int(os.path.splitext(f[len(name):])[0]) for f in matched_files]
		if not versions:
			return 0
		return max(versions)		

	def __init__(self):
		try:
			
			self.DB_NAME = reader['name'] if reader['name'] is not None else 'myvideos93'
			self.DB_USER = reader['user']
			self.DB_PASS = reader['pass']
			self.DB_ADDRESS = reader['host'] #+ ':' + reader['port']
			self.DB_PORT=reader['port']
		  
			if reader['type'] == 'mysql' and \
							self.DB_ADDRESS is not None and \
							self.DB_USER is not None and \
							self.DB_PASS is not None and \
							self.DB_NAME is not None:
				'''			
				conn = mysql.connector.connect(	user=self.DB_USER, \
											password=self.DB_PASS, \
											host=self.DB_ADDRESS, \
											port=self.DB_PORT)
				try:
					cur = conn.cursor()
					cur.execute('SHOW DATABASES')
					bases = cur.fetchall()
					for base in bases:
						print base
					
				finally:
					conn.close()
				'''
		  
				xbmc.log('kodidb: Service: Loading MySQL as DB engine')
				self.DB = 'mysql'
			else:
				xbmc.log('kodidb: Service: MySQL not enabled or not setup correctly')
				raise ValueError('MySQL not enabled or not setup correctly')
		except:
			self.DB = 'sqlite'
			self.db_dir = os.path.join(xbmc.translatePath(BASE_PATH), 'MyVideos%s.db' % VideoDatabase.find_last_version('MyVideos'))
			
	def create_connection(self):
		if self.DB == 'mysql':
			import mysql.connector
			return mysql.connector.connect(	database=self.DB_NAME, \
											user=self.DB_USER, \
											password=self.DB_PASS, \
											host=self.DB_ADDRESS, \
											port=self.DB_PORT, \
											buffered=True)
		else:
			from sqlite3 import dbapi2 as db_sqlite
			return db_sqlite.connect(self.db_dir)
			
	def sql_request(self, req):
		if self.DB == 'mysql':
			return req.replace('?', '%s')
		else:
			return req.replace('%s', '?')
	
class KodiDB(object):
	
	def debug(self, msg, line=0):
		if isinstance(msg, unicode):
			msg = msg.encode('utf-8')
		#line = inspect.currentframe().f_back.f_back.f_lineno
		print '[KodiDB:%d] %s' % (line, msg)
	
	def __init__(self, strmName, strmPath, pluginUrl):
		
		self.debug('strmName: ' + strmName, lineno())
		self.debug('strmPath: ' + strmPath, lineno())
		self.debug('pluginUrl: ' + pluginUrl, lineno())
		
		self.timeOffset	= 0
		
		self.strmName 	= strmName
		self.strmPath 	= strmPath
		self.pluginUrl 	= pluginUrl
		
		self.videoDB = VideoDatabase()
	
	def PlayerPreProccessing(self):
		xbmc.sleep(1000)
		self.db = self.videoDB.create_connection()
		try:
			self.debug('PlayerPreProccessing: ', lineno())
			strmItem = self.getFileItem(self.strmName, self.strmPath)
			if not strmItem is None:
				self.debug('\tstrmItem = ' + str(strmItem), lineno())
				bookmarkItem = self.getBookmarkItem(strmItem['idFile'])
				self.debug('\tbookmarkItem = ' + str(bookmarkItem), lineno())
				self.timeOffset = bookmarkItem['timeInSeconds'] if bookmarkItem != None else 0
				self.debug('\ttimeOffset: ' + str(self.timeOffset / 60) , lineno())
			else:
				self.debug('\tstrmItem is None', lineno())
		finally:
			self.db.close()
	
	def PlayerPostProccessing(self):
		self.db = self.videoDB.create_connection()
		try:
			self.debug('PlayerPostProccessing: ', lineno())
			pluginItem = self.getFileItem(self.pluginUrl)
			self.debug('\tpluginItem = ' + str(pluginItem), lineno())
			strmItem = self.getFileItem(self.strmName, self.strmPath)
			self.debug('\tstrmItem = ' + str(strmItem), lineno())
			
			self.CopyWatchedStatus(pluginItem, strmItem)
			self.ChangeBookmarkId(pluginItem, strmItem)

		finally:
			self.db.close()
		
		
	def CopyWatchedStatus(self, pluginItem, strmItem ):
	
		if pluginItem is None or strmItem is None:
			return

		if pluginItem['playCount'] is None or strmItem['idFile'] is None:
			return
		
		cur = self.db.cursor()

		sql = 	'UPDATE files'
		sql += 	' SET playCount=' + str(pluginItem['playCount'])
		sql += 	' WHERE idFile = ' + str(strmItem['idFile'])
		
		self.debug('CopyWatchedStatus: ' + sql, lineno())
		
		cur.execute(sql)
		self.db.commit()
		
	def ChangeBookmarkId(self, pluginItem, strmItem ):
		if pluginItem is None or strmItem is None:
			return
			
		if strmItem['idFile'] is None or pluginItem['idFile'] is None:
			return
	
		cur = self.db.cursor()
		
		#delete previous
		sql = "DELETE FROM bookmark WHERE idFile=" + str(strmItem['idFile'])
		self.debug('ChangeBookmarkId: ' + sql, lineno())
		cur.execute(sql)
		self.db.commit()
		

		#set new
		sql =  'UPDATE bookmark SET idFile=' + str(strmItem['idFile'])
		sql += ' WHERE idFile = ' +  str(pluginItem['idFile'])
		self.debug('ChangeBookmarkId: ' + sql, lineno())
		
		cur.execute(sql)
		self.db.commit()
		
	def getBookmarkItem(self, idFile):
		cur = self.db.cursor()
		sql =	"SELECT idBookmark, idFile, timeInSeconds, totalTimeInSeconds " + \
				"FROM bookmark WHERE idFile = " + str(idFile)
		cur.execute(sql)
		bookmarks = cur.fetchall()
		for item in bookmarks:
			self.debug('Bookmark: ' + item.__repr__(), lineno())
			return { 'idBookmark': item[0], 'idFile': item[1], 'timeInSeconds': item[2], 'totalTimeInSeconds': item[3] }
			
		return None
		
	def getFileItem(self, strFilename, strPath = None):
		cur = self.db.cursor()
		
		sql = 	"SELECT idFile, idPath, strFilename, playCount, lastPlayed " + \
				"FROM files WHERE strFilename" + \
				"='" + strFilename.replace("'", "''")	+ "'" #.split('&nfo=')[0] + "%'"
		self.debug(sql, lineno())
		cur.execute(sql)
		files = cur.fetchall()
		
		if len(files) == 0:
			self.debug('getFileItem: len(files) == 0', lineno())
			return None

		if strPath is None:
			for item in files:
				self.debug('File: ' + item.__repr__(), lineno())
				return { 'idFile': item[0], 'idPath': item[1], 'strFilename': item[2], 'playCount': item[3], 'lastPlayed': item[4] }
		else:
			sql = 'SELECT idPath, strPath FROM path WHERE idPath IN ( '
			ids = []
			for item in files:
				ids.append( str( item[1]))
			sql += ', '.join(ids) + ' )'
			self.debug(sql, lineno())
			cur.execute(sql)
			paths = cur.fetchall()
			for path in paths:
				#pattern = path[1].replace('\\', '/').replace('[', '\\[').replace(']', '\\]')
				if path[1].replace('\\', '/').endswith(strPath + '/') or path[1].replace('/', '\\').endswith(strPath + '\\'):
					for item in files:
						if path[0] == item[1]:
							self.debug('File: ' + item.__repr__(), lineno())
							return { 'idFile': item[0], 'idPath': item[1], 'strFilename': item[2], 'playCount': item[3], 'lastPlayed': item[4] }
		
		self.debug('return None', lineno())
		return None
		
	def getPathId(self, strPath):
		cur = self.db.cursor()
		
		sql = 	"SELECT idPath, strPath FROM path " + \
				"WHERE strPath LIKE '%" + strPath.encode('utf-8').replace("'", "''") + "%'"
		self.debug(sql, lineno())
		cur.execute(sql)
		return cur.fetchall()
		
	def getFileDataById(self, fileId):
		return
		
		
