#!/usr/bin/env python3
"""
//  -------------------------------------------------------------
//  author        Giga
//  project       qeeqbox/social-analyzer
//  email         gigaqeeq@gmail.com
//  description   app.py (CLI)
//  licensee      AGPL-3.0
//  -------------------------------------------------------------
//  contributors list qeeqbox/social-analyzer/graphs/contributors
//  -------------------------------------------------------------
"""

from logging import getLogger, DEBUG, StreamHandler, Formatter
from logging.handlers import RotatingFileHandler
from sys import stdout
from os import path, makedirs
from requests import get, packages
from time import time
from argparse import ArgumentParser
from json import load
from uuid import uuid4
from tld import get_fld
from functools import wraps
from bs4 import BeautifulSoup
from json import dumps
from pygments import highlight, lexers, formatters
from re import sub as resub
from copy import deepcopy
from contextlib import suppress
from langdetect import detect
from urllib3.exceptions import InsecureRequestWarning
from concurrent.futures import ThreadPoolExecutor, as_completed
from random import randint
from time import sleep

packages.urllib3.disable_warnings(category=InsecureRequestWarning)

WEBSITES_ENTRIES = []
SHARED_DETECTIONS = []
GENERIC_DETECTION = []
LOG = getLogger("social-analyzer")
SITES_PATH = path.join("data","sites.json")
LANGUAGES_PATH = path.join("data","languages.json")
LANGUAGES_JSON = {}
WORKERS = 15

with open(LANGUAGES_PATH) as f:
	LANGUAGES_JSON =  load(f)

def delete_keys(object,keys):
	for key in keys:
		with suppress(Exception):
			del object[key]
	return object

def clean_up_item(object,keys_str):
	with suppress(Exception):
		del object["image"]
	if keys_str == "" or keys_str == None:
		with suppress(Exception):
			del object["text"]
	else:
		for key in object.copy():
			if key not in keys_str:
				with suppress(Exception):
					del object[key]
	return object

def get_language_by_guessing(text):
	try:
		lang = detect(text)
		if lang and lang != "":
			return LANGUAGES_JSON[lang] + " (Maybe)"
	except:
		pass
	return "unavailable"

def get_language_by_parsing(source):
	try:
		lang = BeautifulSoup(source, "html.parser").find("html",attrs={"lang":True})["lang"]
		if lang and lang != "":
			return LANGUAGES_JSON[lang]
	except:
		pass
	return "unavailable"

def check_errors(on_off=None):
	def decorator(func):
		@wraps(func)
		def wrapper(*args, **kwargs):
			if on_off:
				try:
					return func(*args, **kwargs)
				except Exception as e:
					pass
					#print(e)
			else:
				return func(*args, **kwargs)
		return wrapper
	return decorator

@check_errors(True)
def setup_logger(uuid=None,file=False):
	if not path.exists("logs"):
		makedirs("logs")
	LOG.setLevel(DEBUG)
	st = StreamHandler(stdout)
	st.setFormatter(Formatter("%(message)s"))
	LOG.addHandler(st)
	if file and uuid:
		fh = RotatingFileHandler("logs/{}".format(uuid))
		fh.setFormatter(Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
		LOG.addHandler(fh)

@check_errors(True)
def init_websites():
	temp_list = []
	with open(SITES_PATH) as f:
		for item in load(f)["websites_entries"]:
			item["selected"] = "false"
			temp_list.append(item)
	return temp_list

@check_errors(True)
def init_shared_detections():
	temp_list = []
	with open(SITES_PATH) as f:
		for item in load(f)["shared_detections"]:
			item["selected"] = "false"
			temp_list.append(item)
	return temp_list

@check_errors(True)
def init_generic_detection():
	temp_list = []
	with open(SITES_PATH) as f:
		for item in load(f)["generic_detection"]:
			item["selected"] = "false"
			temp_list.append(item)
	return temp_list

def get_website(site):
	x = get_fld(site, fix_protocol=True)
	x = x.replace(".{username}","").replace("{username}.","")
	return x

def list_all_websites():
	if len(WEBSITES_ENTRIES) > 0:
		for site in WEBSITES_ENTRIES:
			x = get_fld(site["url"], fix_protocol=True)
			x = x.replace(".{username}","").replace("{username}.","")
			LOG.info(x)

@check_errors(True)
def find_username_normal(req):

	resutls = []

	def fetch_url(site, username, options):
		sleep(randint(1, 99) / 100)
		LOG.info("[Checking] "+ get_fld(site["url"]))
		source = ""

		detection_level = {
		  "extreme": {
			"fast": "normal",
			"slow": "normal,advanced,ocr",
			"detections": "true",
			"count":1,
			"found":2
		  },
		  "high": {
			"fast": "normal",
			"slow": "normal,advanced,ocr",
			"detections": "true,false",
			"count":2,
			"found":1
		  },
		  "current":"high"
		}

		headers = {
			"User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:84.0) Gecko/20100101 Firefox/84.0",
		}


		try:
			response = get(site["url"].replace("{username}", username), timeout=5, headers=headers, verify=False)
			source = response.text
			response.close()
			text_only = "unavailable";
			title = "unavailable";
			temp_profile = {}
			temp_detected = {}
			detections_count = 0

			def merge_dicts(temp_dict):
				result = {}
				for item in temp_dict:
					for key, value in item.items():
						if key in result:
							result[key] += value
						else:
							result[key] = value
				return result

			def detect_logic(detections):
				detections_count = 0
				temp_detected = []
				temp_found = "false"
				temp_profile = {
				  "found": 0,
				  "image": "",
				  "link": "",
				  "rate": "",
				  "title": "",
				  "language": "",
				  "text": "",
				  "type": "",
				  "good":"",
				  "method":""
				}
				for detection in detections:
					temp_found = "false"
					if detection["type"] in detection_level[detection_level["current"]]["fast"] and source != "":
						detections_count += 1
						if detection["string"].replace("{username}", username).lower() in source.lower():
							temp_found = "true"
						if detection["return"] == temp_found:
							temp_profile["found"] += 1
				return temp_profile, temp_detected, detections_count

			def detect():
				temp_profile_all = []
				temp_detected_all = []
				detections_count_all = 0
				for detection in site["detections"]:
					detections_ = []
					if detection["type"] == "shared":
						detections_ = next(item for item in SHARED_DETECTIONS if item["name"] == detection['name'])
						if len(detections_) > 0:
							val1, val2, val3 = detect_logic(detections_["detections"])
							temp_profile_all.append(val1)
							detections_count_all += val3

				val1, val2, val3 = detect_logic(site["detections"])
				temp_profile_all.append(val1)
				detections_count_all += val3
				return merge_dicts(temp_profile_all), temp_detected_all, detections_count_all

			temp_profile, temp_detected, detections_count = detect()

			if temp_profile["found"] >= detection_level[detection_level["current"]]["found"] and detections_count >= detection_level[detection_level["current"]]["count"]:
				temp_profile["good"] = "true"

			with suppress(Exception):
				soup = BeautifulSoup(source, "html.parser")
				[tag.extract() for tag in soup(["head", "title","style", "script", "[document]"])]
				temp_profile["text"] = soup.getText()
				temp_profile["text"] = resub("\s\s+", " ", temp_profile["text"])
				temp_profile["text"] = temp_profile["text"].replace("\n", "").replace("\t", "").replace("\r", "").strip()
			with suppress(Exception):
				temp_profile["language"] = get_language_by_parsing(source)
				if temp_profile["language"] == "unavailable":
					temp_profile["language"] = get_language_by_guessing(temp_profile["text"])
			with suppress(Exception):
				temp_profile["title"] = BeautifulSoup(source, "html.parser").title.string
				temp_profile["title"] = resub("\s\s+", " ", temp_profile["title"])
				temp_profile["title"] = temp_profile["title"].replace("\n", "").replace("\t", "").replace("\r", "").strip()
			if temp_profile["text"] == "":
				temp_profile["text"] = "unavailable"
			with suppress(Exception):
				if detections_count != 0:
					temp_profile["rate"] = "%" + str(round(((temp_profile["found"] / detections_count) * 100), 2))

			temp_profile["link"] = site["url"].replace("{username}", req["body"]["string"]);
			temp_profile["type"] = site["type"]

			if "FindUserProfilesFast" in options and "GetUserProfilesFast" not in options:
				temp_profile["method"] = "find"
			elif "GetUserProfilesFast" in options and "FindUserProfilesFast" not in options:
				temp_profile["method"] = "get"
			elif "FindUserProfilesFast" in options and "GetUserProfilesFast" in options:
				temp_profile["method"] = "all"

			copy_temp_profile = temp_profile.copy()
			return 1,site["url"], copy_temp_profile
		except Exception as e:
			pass

		return None,site["url"],[]

	for i in range(3):
		WEBSITES_ENTRIES[:] = [d for d in WEBSITES_ENTRIES if d.get('selected') == "true"]
		if len(WEBSITES_ENTRIES) > 0:
			with ThreadPoolExecutor(max_workers=WORKERS) as executor:
				future_fetch_url = (executor.submit(fetch_url, site, req["body"]["string"],req["body"]["options"]) for site in WEBSITES_ENTRIES)
				for future in as_completed(future_fetch_url):
					try:
						good, site, data = future.result()
						if good:
							WEBSITES_ENTRIES[:] = [d for d in WEBSITES_ENTRIES if d.get('url') != site]
							resutls.append(data)
						else:
							LOG.info("[Waiting to retry] "+ get_website(site))
					except Exception as e:
						pass


	WEBSITES_ENTRIES[:] = [d for d in WEBSITES_ENTRIES if d.get('selected') == "true"]
	if len(WEBSITES_ENTRIES) > 0:
		for site in WEBSITES_ENTRIES:
			temp_profile = {"link": "",
							"method":"failed"}
			temp_profile["link"] = site["url"].replace("{username}", req["body"]["string"]);
			resutls.append(temp_profile)
	return resutls

@check_errors(True)
def check_user_cli(argv):
	temp_detected = {"detected":[],"unknown":[],"failed":[]}
	temp_keys = {"found": 0,"link": "","rate": "","title": "","text": ""};
	temp_options = "GetUserProfilesFast,FindUserProfilesFast"
	if argv.method != "":
		if argv.method == "find":
			temp_options = "FindUserProfilesFast"
		if argv.method == "get":
			temp_options = "GetUserProfilesFast"

	req = {"body": {"uuid": str(uuid4()),"string": argv.username,"options": temp_options}}
	setup_logger(req["body"]["uuid"],True)

	if argv.websites == "all":
		for site in WEBSITES_ENTRIES:
			site["selected"] = "true"
	else:
		for site in WEBSITES_ENTRIES:
			for temp in argv.websites.split(" "):
				if temp in site["url"]:
					site["selected"] = "true"

	resutls = find_username_normal(req)

	for item in resutls:
		if item != None:
			if item["method"] == "all":
				if item["good"] == "true":
					item = delete_keys(item,["method","good"])
					item = clean_up_item(item,argv.options)
					temp_detected["detected"].append(item)
				else:
					item = delete_keys(item,["found","rate","method","good"])
					item = clean_up_item(item,argv.options)
					temp_detected["unknown"].append(item)
			elif item["method"] == "find":
				if item["good"] == "true":
					item = delete_keys(item,["method","good"])
					item = clean_up_item(item,argv.options)
					temp_detected["detected"].append(item)
			elif item["method"] == "get":
				item = delete_keys(item,["found","rate","method","good"])
				item = clean_up_item(item,argv.options)
				temp_detected["unknown"].append(item)
			else:
				item = delete_keys(item,["found","rate","method","good","text","title","language","rate"])
				item = clean_up_item(item,argv.options)
				temp_detected["failed"].append(item)

	if len(temp_detected["detected"]) == 0:
	   del temp_detected["detected"]

	if len(temp_detected["unknown"]) == 0:
	   del temp_detected["unknown"];

	if len(temp_detected["failed"]) == 0:
	   del temp_detected["failed"];

	if argv.output == "pretty" or argv.output == "":
		if 'detected' in temp_detected:
			LOG.info("\n[Detected] {} Profile[s]\n".format(len(temp_detected['detected'])));
			for item in temp_detected['detected']:
				LOG.info(highlight(dumps(item, sort_keys=True, indent=4), lexers.JsonLexer(), formatters.TerminalFormatter()))
		if 'unknown' in temp_detected:
			LOG.info("\n[unknown] {} Profile[s]\n".format(len(temp_detected['unknown'])));
			for item in temp_detected['unknown']:
				LOG.info(highlight(dumps(item, sort_keys=True, indent=4), lexers.JsonLexer(), formatters.TerminalFormatter()))
		if 'failed' in temp_detected:
			LOG.info("\n[failed] {} Profile[s]\n".format(len(temp_detected['failed'])));
			for item in temp_detected['failed']:
				LOG.info(highlight(dumps(item, sort_keys=True, indent=4), lexers.JsonLexer(), formatters.TerminalFormatter()))

	if argv.output == "json":
		print(dumps(temp_detected, sort_keys=True, indent=None))

def msg(name=None):
	return """python3 app.py --cli --mode 'fast' --username 'johndoe' --websites 'youtube pinterest tumblr' --output 'pretty'"""

WEBSITES_ENTRIES = init_websites()
SHARED_DETECTIONS = init_shared_detections()
GENERIC_DETECTION = init_websites()

arg_parser = ArgumentParser(description="Qeeqbox/social-analyzer - API and Web App for analyzing & finding a person's profile across 300+ social media websites (Detections are updated regularly)",usage=msg())
arg_parser._action_groups.pop()
arg_parser_required = arg_parser.add_argument_group("Required Arguments")
arg_parser_required.add_argument("--cli",action="store_true", help="Turn this CLI on", required=True)
arg_parser_required.add_argument("--username", help="E.g. johndoe, john_doe or johndoe9999", metavar="", required=True)
arg_parser_required.add_argument("--websites", help="Website or websites separated by space E.g. youtube, tiktok or tumblr", metavar="" ,required=True)
arg_parser_required.add_argument("--mode", help="Analysis mode E.g.fast -> FindUserProfilesFast, slow -> FindUserProfilesSlow or special -> FindUserProfilesSpecial", metavar="", required=True)
arg_parser_optional = arg_parser.add_argument_group("Optional Arguments")
arg_parser_optional.add_argument("--output", help="Show the output in the following format: json -> json output for integration or pretty -> prettify the output", metavar="", default="")
arg_parser_optional.add_argument("--options", help="Show the following when a profile is found: link, rate, title or text", metavar="", default="")
arg_parser_required.add_argument("--method", help="find -> show detected profiles, get -> show all profiles regardless detected or not, both -> combine find & get", metavar="", default="all")
arg_parser_list = arg_parser.add_argument_group("Listing websites & detections")
arg_parser_list.add_argument("--list", action="store_true",  help="List all available websites")
argv = arg_parser.parse_args()

if argv.output != "json":
	print("[!] Detections are updated very often, make sure to get the most up-to-date ones")

if argv.cli:
	if argv.list:
		setup_logger()
		list_all_websites()
	elif argv.mode == "fast":
		if argv.username != "" and argv.websites != "":
			check_user_cli(argv)
