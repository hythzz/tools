from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common import exceptions as EX
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import re
import os
import pickle



class element_has_css_class:
	def __init__(self, element, css_class):
		self.element = element
		self.css_class = css_class


	def __call__(self, driver):
		if self.css_class in self.element.get_attribute("class"):
			return self.element
		else:
			return False



class RecordParser:
	def __init__(self, shortwait, midwait, longwait):
		self.profile_path_name = os.path.join(os.environ['LOCALAPPDATA'], "Google\\Chrome\\User Data")
		self.maplisturl = "https://osu.ppy.sh/beatmapsets?played=played&sort=difficulty_desc&s=any"
		self.osu_log_name = "osu!_standard_record.csv"
		self.mania_log_name = "osu!_mania_record.csv"
		self.tmpdata = ".mapwip.dump"

		# open osu! played page
		self.chrome_options = webdriver.ChromeOptions()
		self.chrome_options.add_argument("--user-data-dir={}".format(self.profile_path_name))
		self.driver = webdriver.Chrome(options=self.chrome_options)
		self.driver.maximize_window()
		self.driver.get(self.maplisturl)
		# need supporter tag
		assert "Filtering by Played requires an active" not in self.driver.page_source

		# misc
		self.wait = WebDriverWait(self.driver, longwait)
		self.midwait = WebDriverWait(self.driver, midwait)
		self.shortwait = WebDriverWait(self.driver, shortwait)
		self.counter = 0
		self.default_trial = 5
		self.mappool = set()

		# get parse beatmap info while scroll down
		self.parseBeatmapList()
		self.driver.quit()

		if os.path.isfile(self.tmpdata):
			os.remove(self.tmpdata)


	def openmap(self, mapurl):
		if self.counter == 0:
			self.driver.execute_script('window.open("{}","_blank");'.format(mapurl))
			self.shortwait.until(EC.number_of_windows_to_be(2))
			self.driver.switch_to.window(window_name=self.driver.window_handles[1])
		else:
			self.driver.switch_to.window(window_name=self.driver.window_handles[1])
			self.driver.get(mapurl)


	def backmain(self):
		self.driver.switch_to.window(window_name=self.driver.window_handles[0])


	def parseBeatmapList(self):
		urlexpr = r'https\:\/\/osu\.ppy\.sh\/beatmapsets\/(\d+)'
		playRecord = []

		# load checkpoint
		if os.path.isfile(self.tmpdata):
			with open(self.tmpdata, 'rb') as fd:
				self.mappool = pickle.load(fd)
		else:
			try:
				os.remove(self.osu_log_name)
				os.remove(self.mania_log_name)
			except FileNotFoundError:
				pass

		while True:
			elems = self.driver.find_elements_by_class_name("beatmapset-panel__header")
			for elem in elems:
				result = re.match(urlexpr, elem.get_attribute("href"))
				mapurl = result.group(0)
				mapid = int(result.group(1))
				if mapid in self.mappool:
					continue

				# get records of a map
				trial = self.default_trial
				while trial > 0:
					trial -= 1
					self.openmap(mapurl)
					playRecord = self.parseBeatmap(mapurl)
					if playRecord is None:
						print("Timeout, try another time, {} of trial left".format(trial))
					else:
						break
				if playRecord is None:
					raise EX.TimeoutException("Timeout in total {} of trials".format(self.default_trial))
				self.writeFile(playRecord)
				self.backmain()

				# record what has been done
				self.mappool.add(mapid)
				with open(self.tmpdata, 'wb') as fd:
					pickle.dump(self.mappool, fd)

				# progress reort
				self.counter += 1
				if self.counter % 20 == 0:
					print("{} of beatmap logs collected".format(self.counter))

			# check if reaching the end
			try:
				self.driver.find_element_by_css_selector("button.show-more-link.show-more-link--beatmapsets.show-more-link--t-ddd")
			except EC.NoSuchElementException:
				isbottom = self.driver.execute_script('''
        			const windowHeight = "innerHeight" in window ? window.innerHeight : document.documentElement.offsetHeight;
        			const body = document.body;
        			const html = document.documentElement;
        			const docHeight = Math.max(body.scrollHeight, body.offsetHeight, html.clientHeight, html.scrollHeight, html.offsetHeight);
        			const windowBottom = windowHeight + window.pageYOffset;
					return (windowBottom >= docHeight);
				''')
				if isbottom:
					break

			# emulate scrolling
			self.driver.execute_script('arguments[0].scrollIntoView(true);', elems[-1])
			self.wait.until_not(EC.presence_of_element_located((By.CSS_SELECTOR, "div.span.beatmapsets__paginator.data-disable")))
			try:
				self.midwait.until(EC.staleness_of(elems[-1]))
			except EX.TimeoutException:
				pass


	def parseBeatmap(self, url):
		title = self.driver.find_element_by_class_name("beatmapset-header__details-text--title").text
		# only parse osu and mania
		allmodes = self.driver.find_elements_by_css_selector("a.game-mode-link")
		chosen_modes = [allmodes[0], allmodes[-1]]

		playRecord = []
		for modetab in chosen_modes:
			# check if mode exists
			if "game-mode-link--disabled" in modetab.get_attribute("class"):
				continue
			try:
				modetab.find_element_by_css_selector("span.game-mode-link__badge")
			except EX.NoSuchElementException:
				continue

			modetab.click()
			mode = self.shortwait.until(element_has_css_class(modetab, "game-mode-link--active")).get_attribute("data-mode")
			scoreboard = self.driver.find_element_by_class_name("beatmapset-scoreboard__main")
			maps = self.driver.find_elements_by_class_name("beatmapset-beatmap-picker__beatmap")

			for amap in maps:
				amap.click()
				self.shortwait.until(element_has_css_class(amap, "beatmapset-beatmap-picker__beatmap--active"))

				# assume got stale record
				try:
					self.wait.until_not(element_has_css_class(scoreboard, "beatmapset-scoreboard__main--loading"))
				except EX.TimeoutException:
					return
				records = self.driver.find_elements_by_class_name("beatmap-scoreboard-top__item")
				try:
					self.shortwait.until(EC.staleness_of(records[0]))
				except EX.TimeoutException:
					pass
				records = self.driver.find_elements_by_class_name("beatmap-scoreboard-top__item")
				if len(records) == 1:
					continue

				# get difficulty
				difficulty = self.driver.find_element_by_class_name("beatmapset-header__diff-name").text

				# get score, acc, combo
				record = records[1]
				results = record.find_elements_by_class_name("beatmap-score-top__stat")
				for result in results:
					header = result.find_element_by_class_name("beatmap-score-top__stat-header")
					if header.text == "TOTAL SCORE":
						score = result.find_element_by_class_name("beatmap-score-top__stat-value").text
					elif header.text == "ACCURACY":
						acc = result.find_element_by_class_name("beatmap-score-top__stat-value").text
					elif header.text == "MAX COMBO":
						combo = result.find_element_by_class_name("beatmap-score-top__stat-value").text

				# get mod
				modWrap = record.find_element_by_css_selector("div.beatmap-score-top__stat-value.beatmap-score-top__stat-value--mods")
				try:
					modElems = modWrap.find_elements_by_class_name("mod")
					modexpr = r'mod--([A-Z1-9]{2})'

					mods = []
					for modElem in modElems:
						css_class = modElem.get_attribute("class")
						amod = re.search(modexpr, css_class).group(1)
						mods.append(amod)

					if len(mods) == 0:
						raise EX.NoSuchElementException
					mod = ','.join(mods)
				except EX.NoSuchElementException:
					mod = "None"

				# get rank
				rankElem = record.find_element_by_css_selector("div.score-rank.score-rank--tiny")
				rankclass = rankElem.get_attribute("class")
				rankexpr = r'score-rank score-rank--tiny score-rank--([XSABCDH]+)'
				rank = re.match(rankexpr, rankclass).group(1)

				# get date
				dateElem = record.find_element_by_tag_name("time")
				date = dateElem.get_attribute("datetime")

				# formating
				score = score.replace(',', '')
				combo = combo[:-1].replace(',', '')
				dateexpr = r'\d+-\d+-\d+'
				date = re.match(dateexpr, date).group(0)
				playRecord.append((mode, title, url, difficulty, score, acc, combo, mod, rank, date))

		return playRecord


	def writeFile(self, records):
		osu_output = u''
		mania_output = u''
		for record in records:
			if record[0] == "osu":
				osu_output += '\t'.join(record[1:])
				osu_output += '\n'
			else:
				mania_output += '\t'.join(record[1:])
				mania_output += '\n'

		with open(self.osu_log_name, 'ab+') as fd:
			fd.write(osu_output.encode('UTF-8'))
		with open(self.mania_log_name, 'ab+') as fd:
			fd.write(mania_output.encode('UTF-8'))



if __name__ == "__main__":
	RecordParser(1, 3, 15)