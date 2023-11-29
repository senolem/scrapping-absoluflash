import requests
from bs4 import BeautifulSoup
from bs4.element import NavigableString
import re
import html
import codecs
from urllib.parse import urlparse, urljoin
import traceback

url = "https://absoluflash.co/jeux-adresse/"

visited_urls = set()
visited_urls.add("https://absoluflash.co/jeux-adresse/index.shtml")

def get_page_content(url):
	response = requests.get(url)
	if response.status_code == 200:
		return response.content
	else:
		raise Exception(f"Failed to fetch page content from {url}")

def extract_description(element):
	p_element = element.find('p')
	if p_element:
		return p_element.get_text(separator=' ', strip=True)
	else:
		title_element = element.find('span', class_='titre')
		if title_element:
			title = title_element.text.strip()
			description_parts = []
			for sibling in title_element.next_siblings:
				if sibling == title_element:
					break
				if sibling.name == 'center':
					break
				if sibling.name is None:
					text = sibling.strip()
					if title not in text:
						description_parts.append(text)
			description = ' '.join(description_parts)
			return description
	return ''

def extract_variable_value(content, variable_name):
	pattern = r"var\s+" + variable_name + r"\s*=\s*['\"]([^'\"]+)['\"]"
	match = re.search(pattern, content)
	if match:
		print(f"var = {match.group(1)}")
		return match.group(1)
	return ''

def extract_data_from_page(content, category):
	variables = {}
	soup = BeautifulSoup(content, 'html.parser')
	script_elements = soup.find_all('script')
	for script in script_elements:
		script_content = script.string
		if script_content:
			matches = re.findall(r"var\s+([^=]+)\s*=\s*['\"]([^'\"]+)['\"]", script_content)
			for variable, value in matches:
				variables[variable] = value
	variables["p011164"] = "check1point"
	data = []
	tubeverti_elements = soup.find_all('td', class_='tubeverti')
	for tubeverti in tubeverti_elements:
		tr_elements = tubeverti.find_all('tr')
		for tr in tr_elements:
			description = ""
			img = ""
			img2 = ""
			width = ""
			height = ""
			td_elements = tr.find_all('td')
			if len(td_elements) >= 2:
				img_element = td_elements[0].find_all('img')
				span_element = td_elements[1].find('span', class_='titre')
				if img_element and span_element:
					for i, image in enumerate(img_element):
						if image and image.has_attr('src'):
							if i == 0:
								img = image['src']
							elif i == 1:
								img2 = image['src']
							else:
								print("image error!")
								break
					title = span_element.text.strip()
					description = extract_description(td_elements[1])
					description = description.replace(title, '').strip()
					link = ""
					href = td_elements[1].find('a')
					onclick_value = ""
					if href and href.has_attr('onclick'):
						onclick_value = href.get('onclick')
					if onclick_value:
						resolved_value = onclick_value
						to_resolve_dict = re.findall(r'\+\s*([^+]+)\s*\+', onclick_value)
						if to_resolve_dict:
							for to_resolve in to_resolve_dict:
								if to_resolve in variables:
									resolved_value = resolved_value.replace('+' + to_resolve + '+', variables[to_resolve])
									resolved_value = resolved_value.replace("'" + variables[to_resolve] + "'", variables[to_resolve])
									match = re.search(r"window.open\('([^']+)", resolved_value)
									if match:
										url_variable = match.group(1)
										url_variable = resolve_variables(variables, url_variable)
										link = url_variable
										width_match = re.search(r"w=(\d+)", onclick_value)
										height_match = re.search(r"h=(\d+)", onclick_value)
										width = width_match.group(1) if width_match else ''
										height = height_match.group(1) if height_match else ''
						else:
							match = re.search(r"window.open\('([^']+)", resolved_value)
							if match:
								link = match.group(1)
							else:
								print(resolved_value)
								print(href)
					elif href.has_attr('href'):
						link = href.get('href')
					marks_info = extract_info(td_elements[1])
					playability_info = marks_info[0]
					graphism_info = marks_info[1]
					interest_info = marks_info[2]
					title = html.escape(title).replace("'", "''")
					description = html.escape(description).replace("'", "''")
					link = link.replace("'", "''")
					playability_info = html.escape(playability_info).replace("'", "''")
					graphism_info = html.escape(graphism_info).replace("'", "''")
					interest_info = interest_info.replace("'", "''") if interest_info else ''

					data.append((title, description, link, playability_info, graphism_info, interest_info, width, height, img, img2, category))
	return data

def extract_info(td_element):
	playability_info = ""
	graphism_info = ""
	interest_info = ""

	# Find all the nodes within the td element
	nodes = [node for node in td_element.recursiveChildGenerator() if isinstance(node, NavigableString) or node.name == 'img']

	# Process the nodes to extract the desired information
	for i, node in enumerate(nodes):
		if "Jouabilité" in node:
			playability_info = node.split(":")[-1].strip()
		elif "Graphisme" in node:
			graphism_info = node.split(":")[-1].strip()
		elif "Intérêt" in str(node):
			interest_parts = nodes[i:]
			interest_info = ''.join(str(part) for part in interest_parts).strip()

	return playability_info, graphism_info, interest_info

def generate_sql_file(data):
	sql_statements = []
	sql_create_table = "CREATE TABLE IF NOT EXISTS test (id INT AUTO_INCREMENT PRIMARY KEY, title VARCHAR(255), description TEXT, link VARCHAR(255), playability_info VARCHAR(255), graphism_info VARCHAR(255), interest_info TEXT, width INT, height INT, img VARCHAR(255), img2 VARCHAR(255), category VARCHAR(255));"
	sql_statements.append(sql_create_table)

	for entry in data:
		sql = f"INSERT INTO test (category; title, description, link, playability_info, graphism_info, interest_info, width, height, img, img2, category) VALUES "
		sql += f"('{entry[0]}', '{entry[1]}', '{entry[2]}', '{entry[3]}', '{entry[4]}', '{entry[5]}', '{entry[6]}', '{entry[7]}', '{entry[8]}', '{entry[9]}', '{entry[10]}');"
		sql_statements.append(sql)

	with open('output.sql', 'w') as file:
		file.write('\n'.join(sql_statements))


def resolve_variables(variables, value):
	for variable in re.findall(r'\+\s*([^+]+)\s*\+', value):
		if variable in variables:
			value = value.replace('+' + variable + '+', variables[variable])
	return value

def scrape_website(url, data, category=None):
	try:
		if url in visited_urls:
			return data  # Skip scraping if URL has already been visited

		visited_urls.add(url)  # Mark URL as visited
		content = get_page_content(url)
		page_data = extract_data_from_page(content, category)
		data.extend(page_data)
		print(f"Scraped {url}")

		# Follow and scrape links within the same folder
		soup = BeautifulSoup(content, 'html.parser')
		links = soup.find_all('a', href=True)
		for link in links:
			href = link['href']
			parsed_url = urlparse(href)
			if not parsed_url.netloc:  # Check if it's a relative URL
				absolute_url = urljoin(url, href)
				if url in absolute_url:  # Ensure it's within the same folder
					folder_name = urlparse(url).path.split('/')[-2]
					data = scrape_website(absolute_url, data, category=folder_name)
	except Exception as e:
		print(traceback.format_exc())
	return data

if __name__ == "__main__":
	data = []
	folder_name = urlparse(url).path.split('/')[-2]  # Extract the current folder name
	scrape_website(url, data, category=folder_name)
	generate_sql_file(data)
	print("Scraping completed successfully!")



