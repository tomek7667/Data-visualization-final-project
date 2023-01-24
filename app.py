import requests
import json
import os
import folium
import kmeans1d
import wikipediaapi
import re

voivodeships = ['dolnośląskie', 'kujawsko-pomorskie', 'lubelskie', 'lubuskie', 'łódzkie',
				'małopolskie', 'mazowieckie', 'opolskie', 'podkarpackie', 'podlaskie', 'pomorskie', 
				'śląskie', 'świętokrzyskie', 'warmińsko-mazurskie', 'wielkopolskie', 'zachodniopomorskie']

feature_types = {}

def load_geometry():
	use_cache = os.path.exists('geometry.json')
	if use_cache:
		with open('geometry.json', 'r') as f:
			data = json.loads(f.read())
		return data
	else:
		with open('geometry.json', 'w') as f:
			d = {}
			url = 'https://nominatim.openstreetmap.org/search.php'
			for voivodeship in voivodeships:
				params = {'format': 'geojson', 'polygon_geojson': 1, 'q': f"województwo {voivodeship}"}
				response = requests.get(url, params=params)
				data = response.json()
				d[voivodeship] = {}
				d[voivodeship]["coordinates"] = data['features'][0]['geometry']['coordinates']
				d[voivodeship]["osmtype"] = data['features'][0]['properties']['osm_type'][0].upper()
				d[voivodeship]["osmid"] = data['features'][0]['properties']['osm_id']
				feature_types[voivodeship] = data
			open("feature_types.json", "w").write(json.dumps(feature_types))
			f.write(json.dumps(d))
			return d

def load_population(geometry_data):
	use_cache = os.path.exists('population.json')
	if use_cache:
		with open('population.json', 'r') as f:
			data = json.loads(f)
		return data
	else:
		with open('population.json', 'w') as f:
			d = {}
			url = 'https://nominatim.openstreetmap.org/details.php'
			for voivodeship in voivodeships:
				params = {'format': 'json', 'osmtype': geometry_data[voivodeship]['osmtype'], 'osmid': geometry_data[voivodeship]['osmid'], 'class': 'boundary'}
				response = requests.get(url, params=params)
				data = response.json()
				d[voivodeship] = {}
				d[voivodeship]["population"] = int(data['extratags']['population'])
			f.write(json.dumps(d))
			return d

# 1. Find polygons for each voivodeship in Poland.
geometry_data = load_geometry()
print("[+] Geometry data Loaded!")
# 2. Find population data per each voivodeship.
population_data = load_population(geometry_data)
print("[+] Population data Loaded!")
# Merge the data:
merged = {}
for voivodeship in voivodeships:
	merged[voivodeship] = {}
	merged[voivodeship]['population'] = population_data[voivodeship]['population']
	merged[voivodeship]['coordinates'] = geometry_data[voivodeship]['coordinates']
# Save the data:
with open('merged.json', 'w') as f:
	f.write(json.dumps(merged))
print("[+] Merged data saved!")

populations_array = [merged[voivodeship]['population'] for voivodeship in merged]
number_of_clusters = 9

clusters, centroids = kmeans1d.cluster(populations_array, number_of_clusters)
for voivodeship in merged:
	merged[voivodeship]['cluster'] = clusters[voivodeships.index(voivodeship)]
	merged[voivodeship]['centroid'] = centroids[merged[voivodeship]['cluster']]

colors = {}
j = 0
for i in range(0xff, 0, -(0xff // number_of_clusters)):
	colors[j] = f"#{hex(i)[2:]}0000"
	j += 1

for voivodeship in merged:
	merged[voivodeship]['color'] = colors[merged[voivodeship]['cluster']]


# Apply number of cities using wikipediaapi and regex scraping
wiki_wiki = wikipediaapi.Wikipedia('pl')
use_cache = os.path.exists('cities.json')
if use_cache:
	with open('cities.json', 'r') as f:
		merged = json.loads(f.read())
else:
	for v in voivodeships:
		if v == 'podlaskie':
			q = f"Miasta w województwie podlaskim"
			voivodeship_urbanisation = wiki_wiki.page(q)
		elif v == "wielkopolskie":
			q = f"Miasta w województwie wielkopolskim"
			voivodeship_urbanisation = wiki_wiki.page(q)
		else:
			q = f"województwo {v}"
			voivodeship_urbanisation = wiki_wiki.page(q).section_by_title("Urbanizacja")
			if voivodeship_urbanisation is None:
				voivodeship_urbanisation = wiki_wiki.page(q).section_by_title("Miasta")
			if voivodeship_urbanisation is None:
				voivodeship_urbanisation = wiki_wiki.page(q).section_by_title("Ludność i miasta")
		voivodeship_urbanisation = voivodeship_urbanisation.text
		cities_number = int(re.findall(r'\d+ miast', voivodeship_urbanisation)[0].split(' ')[0])
		merged[v]['cities_number'] = cities_number
	with open('cities.json', 'w') as f:
		f.write(json.dumps(merged))

m = folium.Map(location=[52.0, 19.0], zoom_start=6)
for voivodeship in merged:
	coordinates = [(coord[1], coord[0]) for coord in merged[voivodeship]['coordinates'][0]]
	voivodeship_population = merged[voivodeship]['population']
	color = merged[voivodeship]['color']
	cities_number = merged[voivodeship]['cities_number']
	centroid_value = merged[voivodeship]['centroid']
	cluster_number = merged[voivodeship]['cluster']
	popup = folium.Popup(f'Voivodeship name: <b>{voivodeship}</b><br>Population: <b>{voivodeship_population}</b><br>Number of cities in the voivodeship: <b>{cities_number}</b><br>Centroid value: <b>{centroid_value}</b><br>Cluster number: <b>{cluster_number}</b>', max_width=500)
	folium.Polygon(
		coordinates,
		popup=popup,
		tooltip=voivodeship,
		color=color,
		fill=True,
		fill_color=color
	).add_to(m)

print("[+] Map created!")

m.save('map.html')
