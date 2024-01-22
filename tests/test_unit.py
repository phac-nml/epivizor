from app.views import renderHistPlot
import pandas as pd
import pathlib, os,json


ROOT_DIR = os.path.join(pathlib.Path(__file__).parents[1].resolve())
demo_df_filepath = os.path.join(ROOT_DIR,'example','ecoli_sample_data.csv')

from_data_dict={'validatedfields_exp2obs_map': 
                {'age': 'age', 'cluster_id': 'cluster_id', 'date': 'date', 'gender': 'gender', 'genetic_profile': 'genetic_profile', 
                 'geoloc_id': 'geoloc_id', 'hierarchical_subtype': 'hierarchical_subtype', 'investigation_id': 'investigation_id', 
                 'phenotypic_profile': 'phenotypic_profile', 'primary_type': 'primary_type', 'sample_id': 'sample_id', 
                 'secondary_type': 'secondary_type', 'source_site': 'source_site', 'source_type': 'source_type'
                 }, 
                'delimiter_symbol': '|'}
jsonPlotsDict = {'figures': {}, 'captions': {}}

def test_renderHistPlot():
    df=pd.read_csv(demo_df_filepath)
    renderHistPlot(df = df, df_col_name = 'geoloc_id', form_data_dict = from_data_dict, 
                   jsonPlotsDict = jsonPlotsDict, jsonPlotsDictKey = 'geoloc_chart',plot_title = 'Geolocation chart')
    
    json_geo_graph = json.loads(jsonPlotsDict['figures']['geoloc_chart'])
    
    assert json_geo_graph['data'][0]['x'].count('Canada') == 29
    assert json_geo_graph['data'][0]['x'].count('United States') == 394
    assert json_geo_graph['data'][0]['x'].count('unknown') == 138 #missing data is rendered as unknown
