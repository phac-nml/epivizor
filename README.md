[![](https://img.shields.io/badge/render.com-deployed-brightgreen)](https://epivizor.onrender.com/dashboard)
![](https://img.shields.io/github/v/release/phac-nml/epivizor?include_prereleases)
![](https://img.shields.io/github/last-commit/phac-nml/epivizor)
![](https://img.shields.io/github/issues/phac-nml/epivizor)

# Epivizor
Visual genomic epidemiology data analysis web application for hypothesis generation via interactive interfaces.

# Aim
This project aims to create a visualization tool to allow for convenient visual genomic epidemiology data analysis.
It can help in identification of data trends via concurrent analysis of several variables and can augment existing epidemiological clusters by exploring additional metadata trends both inside and outside of a given cluster.

# Context
Foodborne outbreaks are complex and cause significant levels of mortality and illness worldwide. Integrating metadata with genetic information can provide powerful trend insights and potential sources of infection. Yet visualization of this multifaceted complex data can be time consuming and require technical expertise. 

We designed a fast, scalable and flexible web tool for analyzing complex information in convenient dashboard-like interface. Epivizor can be deployed locally on a conventional laptop or dedicated server and was tested to scale to 1M+ rows of metadata.

Enhanced data filtering and subsetting via responsive interface enables users to readily compare trends between several outbreak clusters using gender, source, geography, temporal and/or other variables.

Epivizor addresses a key public health laboratories need to conveniently explore complex metadata, extract useful actionable knowledge and support hypothesis generation in a freely accessible tool that can complement existing workflows.

# Features
- dynamic mapping of input metadata columns to different plot types to explore categorical, temporal, hierarchical genetic data
- easy data filtering and grouping
- compare and contrast mode for two subsets of filtered data
- various visual and data export capabilities for enhanced reporting purposes
- lightweight with minimal amount of dependencies


## Availability
- local installation and deployment from source code
- publicly deployed demo instance at https://epivizor.onrender.com/dashboard (takes 20s to boot)

## Install 
Installation is simple with [minimal set of dependencies](#dependencies)

1. Pull this repository via `git`.
2. Install dependencies from the `requirements.txt` by running `pip3 install -r requirements.txt`

## Run 
Run web application locally either by
- `python3 run.py` or
- `export FLASK_APP=run.py && flask run --host=0.0.0.0 --port=5000` (optionally set `export FLASK_ENV=development` for debugging)

Note that default Flask port is 5000. This port could be changed by specifying the `--port` argument of `flask` or by modifying the `run.py`.

Access the application locally by pointing your browser to `http://localhost:5000`


## Dependencies
- flask
- flask-caching
- pandas
- plotly
- werkzeug
- orjson
- openpyxl
- scipy

## uWSGI server deployment 
Optionally install uWSGI webserver by simply installing  the `uwsgi` package.  Please note that version `>=2.0` is required.

Use `uwsgi.ini` customizable configuration file to run an configure the server. 

`uwsgi --ini uwsgi.ini`


## Sample data
To explore capabilities of the Epivizor various sample datasets are included in in the [`example`](./example) folder

- E.coli synthetic dataset has 1000 samples with both temporal, hierarchical and other metadata information
- Plasmid 


# Authors
 - Kyrylo Bessonov
 - James Robertson
 - Justin Schonfeld

# Contact
If you have questions or suggestions you are welcome to create an [`Issue`](https://github.com/phac-nml/epivizor/issues) or send us an email
- kyrylo.bessonov@phac-aspc.gc.ca
- james.robertson@phac-aspc.gc.ca


# Legal
Copyright Government of Canada 2021

Written by: National Microbiology Laboratory, Public Health Agency of Canada

Licensed under the Apache License, Version 2.0 (the "License"); you may not use this work except in compliance with the License. You may obtain a copy of the License at:

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.



