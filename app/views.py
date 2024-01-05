from app import app
from flask import request, render_template, flash, session, jsonify, Response
from flask_caching import Cache
from werkzeug.utils import secure_filename
from werkzeug.wsgi import FileWrapper
import pandas as pd
import numpy as np
from scipy.stats import pearsonr
from openpyxl import load_workbook
from collections import Counter

# import modin.pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.utils
from plotly.subplots import make_subplots
import json, re, time, itertools
import string, random
from plotly.io.json import to_json_plotly
from io import BytesIO


app.config.from_object("config.ConfigDebug")
cache = Cache(app=app, config={"CACHE_TYPE": "filesystem", 'CACHE_DIR': 'cache-dir', "CACHE_DEFAULT_TIMEOUT": 86400})



def getPlotVariablesDict(form_dict):
    '''
    Extracts submitted variable names and their values from the front end via POST HTTP request and returns a 
    Python dictionary of plot # and variables
    
    Arguments:
        form_dict (dict): a Python dictionary of variable names and values provided by the frontend via POST request
    Returns:
        plotsMetaDataDict (dict): a dictionary of plots and their variable values {"plot#":[variables names list]}
    '''
    plotsMetaDataDict = {} ## {'plottype_p1': 'frequency', 'variable1_p1': 'File Pair ID'}
    for key in [k for k in form_dict.keys() if re.match(r'plottype.*', k)]:
        plotn = re.match(r'.*_p(\d+)', key).group(1)
        plotsMetaDataDict[plotn] = {}
        plotsMetaDataDict[plotn]['plottype'] = form_dict['plottype_p' + plotn]
        plotsMetaDataDict[plotn]['variables'] = list()
        #print([form_dict[k] for k in form_dict.keys() if re.match(r'variable\d+_p' + plotn, k)])
        plotsMetaDataDict[plotn]['variables'] = [form_dict[k] for k in form_dict.keys() if
                                                 re.match(r'variable\d+_p' + plotn, k)]

    return plotsMetaDataDict

def extactFilterValuesFromPOST2Dict(form_filt_values_dict,setname='filterset1'):
    '''
    Extract filter values submitted by the EpiVizor frontend on 14 expected variables and return a dictionary of filtered values
    Arguments:
        form_filter_values_dict - dictionary of filtered 
    Return:
        filter_dict - dictionary of expected variable and associated list of values   
    '''
    filter_dict = {}
    filter_dict['primary_type'] = list()
    filter_dict['secondary_type'] = list()
    filter_dict['genetic_profile'] = list()
    filter_dict['phenotypic_profile'] = list()
    filter_dict['start_date'] = None
    filter_dict['end_date'] = None
    filter_dict['cluster_id'] = list()
    filter_dict['investigation_id'] = list()
    filter_dict['geoloc_id'] = list()
    filter_dict['source_site'] = list()
    filter_dict['source_type'] = list()
    filter_dict['geoloc_id'] = list()

    for formkey in form_filt_values_dict:
        print(formkey)
        if re.match(r'select_primary_type_'+setname+'.*',formkey):
            filter_dict['primary_type'].append(form_filt_values_dict[formkey])
        elif re.match(r'select_secondary_type_'+setname+'.*',formkey):
            filter_dict['secondary_type'].append(form_filt_values_dict[formkey])
        elif re.match(r'select_genetic_profile_'+setname+".*",formkey):
            filter_dict['genetic_profile'].append(form_filt_values_dict[formkey])
        elif re.match(r'select_phenotypic_profile_'+setname+'.*', formkey):
            filter_dict['phenotypic_profile'].append(form_filt_values_dict[formkey])
        elif re.match(r'start_date_'+setname+'.*', formkey):
            filter_dict['start_date'] = re.sub('-', '', form_filt_values_dict[formkey])
        elif re.match(r'end_date_'+setname+'.*', formkey):
            filter_dict['end_date'] = re.sub('-', '', form_filt_values_dict[formkey])
        elif re.match(r'select_cluster_id_'+setname+'.*', formkey):
            filter_dict['cluster_id'].append(form_filt_values_dict[formkey])
        elif re.match(r'select_investigation_id_'+setname+'.*', formkey):
            filter_dict['investigation_id'].append(form_filt_values_dict[formkey])
        elif re.match(r"select_hs_level_\d+_genotype_hierarchy_groups_"+setname+".*", formkey):
            df_column_name = re.match(r"select_(hs_level_\d+)_genotype_hierarchy_groups_"+setname+".*", formkey).group(1)
            if df_column_name not in filter_dict:
                filter_dict[df_column_name] = [form_filt_values_dict[formkey]]
            else:
                filter_dict[df_column_name].append(form_filt_values_dict[formkey])
        elif re.match(r'select_source_site_'+setname+'.*', formkey):
            filter_dict['source_site'].append(form_filt_values_dict[formkey])
        elif re.match(r'select_source_type_'+setname+'.*', formkey):
            filter_dict['source_type'].append(form_filt_values_dict[formkey])
        elif re.match(r'select_geoloc_id_'+setname+'.*', formkey):
            filter_dict['geoloc_id'].append(form_filt_values_dict[formkey])
    return filter_dict


def getFilteredData(filter_dict, df):
    '''
    Filter input dataframe based on the parsed POST dictionary values from EpiVizor frontend filters and obtain new filtered dataframe
    Usually applied to further filter the original input data or to create Group #1 and #2 subsets for comparison purposes
    
    Arguments:
        filter_dict {dict} - dictionary with filter values of form {'expected variable':[val1,val2,....]}.
                            For example, {'primary_type': ['B.1.1.529', 'B.1.1.7'], ...}
        df {pandas dataframe} - dataframe to be filtered on
    Return: 
        df {pandas dataframe} - resulting filtered dataframe according to the supplied filters
    '''
    print(f"getFilteredData() and {','.join(df.columns.to_list())}")
    
    #convert values to REGEX safe equivalents such as 'B\\.1\\.1\\.7 instead of B.1.1.7 where dot is everything
    regex_characters=['\.','\+','\*','\?','\^','\$','\(','\)','\[','\]','\|','\{','\}']
    for variable in [key for key,value in filter_dict.items() if filter_dict[key] is not None]:
            if isinstance(filter_dict[variable],list):
                for character in regex_characters:
                    filter_dict[variable] = [re.sub(character,'\\'+character,i) for i in filter_dict[variable]]
            else:
                for character in regex_characters:
                    filter_dict[variable] = re.sub(character,'\\'+character,filter_dict[variable])
    hs_idx_final=[]
    for selected_hs_filter in [key for key in filter_dict if 'hs_level' in key]:
        print("Hierarchical subtype filter for the sunburst plot is being applied on", df.shape)
        regex = '|'.join(filter_dict[selected_hs_filter])
        idx_bool = (df.loc[:,selected_hs_filter].str.fullmatch(regex) ).to_list()
        if not hs_idx_final:
            hs_idx_final = idx_bool
        else:
            hs_idx_final = [any(tup) for  tup in zip(idx_bool,hs_idx_final)]
          
    if hs_idx_final:
        df = df.loc[hs_idx_final,:].copy()
        print(f"After hierarchical cluster code filter left {df.shape[0]} rows")   

    #The expected variables filters
    if filter_dict['primary_type']:
        df = df.loc[(df['primary_type'].str.fullmatch('|'.join(filter_dict['primary_type']), case=False, na=False))].copy()
    if filter_dict['secondary_type']:
        df = df.loc[(df['secondary_type'].str.fullmatch('|'.join(filter_dict['secondary_type']), case=False, na=False))].copy()
    if filter_dict['genetic_profile']:
        df = df.loc[(df['genetic_profile'].str.fullmatch("|".join(filter_dict['genetic_profile']), case=False, na=False))].copy()
    if filter_dict['phenotypic_profile']:
        df = df.loc[(df['phenotypic_profile'].str.fullmatch("|".join(filter_dict['phenotypic_profile']), case=False, na=False))].copy()
    if filter_dict['cluster_id']:
        df = df.loc[(df['cluster_id'].str.fullmatch('|'.join(filter_dict['cluster_id']), case=False, na=False))].copy()
    if filter_dict['investigation_id']:
        df = df.loc[(df['investigation_id'].str.fullmatch('|'.join(filter_dict['investigation_id']), case=False, na=False))].copy()
    if filter_dict['source_site']:
        df = df.loc[(df['source_site'].str.fullmatch("|".join(filter_dict['source_site']), case=False, na=False))].copy()
    if filter_dict['source_type']:
        df = df.loc[(df['source_type'].str.fullmatch("|".join(filter_dict['source_type']), case=False, na=False))].copy()
    if filter_dict['geoloc_id']:
        df = df.loc[(df['geoloc_id'].str.fullmatch("|".join(filter_dict['geoloc_id']), case=False, na=False))].copy()

    #Date range filter
    if 'date' in df.columns:
        df.loc[:,'date']=pd.to_datetime(df['date'],errors='coerce')
        if filter_dict['start_date'] and filter_dict['end_date']:
            print("date >= " + filter_dict['start_date'] + " and date <= " + filter_dict['end_date'])
            df.query("date >= " + filter_dict['start_date'] + " and date <= " + filter_dict['end_date'], inplace=True)
        elif filter_dict['start_date'] and filter_dict['end_date'] is None:
            df.query("date >= " + filter_dict['start_date'], inplace=True)
        elif filter_dict['start_date'] is None and filter_dict['end_date']:
            df.query("date <= " + filter_dict['end_date'], inplace=True)
    else:
        print('WARNING: the date field "date" not mapped or available so date filtering (if selected) was not applied!')
        
    print("After filtering {}".format(df.shape))
    return df


def renderPlotsFromDict(metadata, form_dict, df):
    """Renders Plotly figure objects for the custom plots view from the input data and returns 

    Arguments:
        metadata (dict): dictionary storing plot number, plot type and its variable names/fields in the following 
                         format {'plot#':{'plottype':'string',variables:['name1',...]}}
        form_dict (dict): dictionary of the supplied filter values from the frontend in a form of key and value pairs encoded to 
                          identify a plot and variable in the following format
                          {'plottype_p#': 'string', 'variable#_p#': 'string', 'filter_div_variable#_p#': 'value'}
        df (pandas dataframe): input pandas dataframe to render plots on

    Returns:
        jsonPlotsDict (dict): Python dictionary of the Plotly figure objects in JSON text format
    """
    jsonPlotsDict = {}
    error_msg = ''

    for nplot in sorted(metadata.keys()):
        print(nplot)
        # filter data IF filters provided in the submitted form
        dfs = []
        for key in form_dict:
            if 'filter' in key and 'p'+nplot in key:
                variable_name = form_dict[re.match(".*(variable\d+_p\d+).*", key).group(1)]
                print(variable_name,type(variable_name),form_dict[key],type(form_dict[key]))
                try:
                    print('`'+variable_name + '`==' + form_dict[key])
                    float(form_dict[key])
                    dfs.append(df.query('`'+variable_name + '`==' + form_dict[key]))
                except Exception as e:
                    print(e)
                    print('`'+variable_name + '`=="' + form_dict[key]+'"')    
                    dfs.append(df.query('`'+variable_name + '`=="' + form_dict[key]+'"'))
        if dfs:
            df = pd.concat(dfs)
            print(df.shape)

        if metadata[nplot]['plottype'] == 'frequency':
            if any([i=='NA' for i in metadata[nplot]['variables']]):
                error_msg = error_msg+'\nERROR: Define a variable for the Pie plot'
                print(error_msg)
                return {"error":error_msg}

            fig = px.histogram(df, x=metadata[nplot]['variables'][0],
                               title="Frequency plot of a variable: {}".format(metadata[nplot]['variables'][0])
                               )
            graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
            jsonPlotsDict[nplot] = graphJSON
        elif metadata[nplot]['plottype'] == 'timeline':
            if any([i=='NA' for i in metadata[nplot]['variables']]):
                error_msg = error_msg+'\nERROR: Select exactly 2 variables for the Timeline plot'
                print(error_msg)
                return {"error":error_msg}


            # define which variable is of type DATE and type CATEGORY
            x_time_var = None
            y_value_cat = None
            for value in metadata[nplot]['variables']:
                try:
                    pd.to_datetime(df[value])
                    x_time_var = value
                except:
                    y_value_cat = value
                    pass

            if any([i == None for i in [x_time_var, y_value_cat]]):
                error_msg = error_msg+"ERROR: Selected variables are of incorrect types. Select date and category variable"
                print(error_msg)
                return {"error":error_msg}

            df_filtered = df[df[y_value_cat].isna() == False]

            # EarliestDate
            fig = px.line(df_filtered.groupby([x_time_var, y_value_cat]).size().reset_index(name="counts"),
                          y="counts", x=x_time_var, color=y_value_cat, render_mode='webgl',
                          title="Timeline plot of variable: {}".format(request.form.get('variable')))
            fig.update_xaxes(rangeslider_visible=True,
                             rangeselector=dict(
                                 buttons=list([
                                     dict(count=1, label="1m", step="month", stepmode="backward"),
                                     dict(count=6, label="6m", step="month", stepmode="backward"),
                                     dict(count=1, label="YTD", step="year", stepmode="todate"),
                                     dict(count=1, label="1y", step="year", stepmode="backward"),
                                     dict(step="all")
                                 ])
                             )
                             )
            # fig.for_each_trace(lambda trace: trace.update(visible="legendonly")) #make categories invisible by default
            fig.update_traces(mode='markers+lines')  # show dots and lines
        
            jsonPlotsDict[nplot] = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

        elif metadata[nplot]['plottype'] == 'pie':
            if any([i=='NA' for i in metadata[nplot]['variables']]):
                error_msg = error_msg+'\nERROR: Define a variable for the Pie plot'
                print(error_msg)
                return {"error":error_msg}
            
            fig = px.pie(df.groupby([metadata[nplot]['variables'][0]]).size().reset_index(name="counts"),
                         names=metadata[nplot]['variables'][0],
                         color=metadata[nplot]['variables'][0], values='counts')
            # fig.update_traces(textinfo='none') #show labels for all slices
            fig.update_traces(textposition='inside', textinfo='label+percent')
            fig.update_layout(uniformtext_minsize=12, uniformtext_mode='hide')
            jsonPlotsDict[nplot] = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
        elif metadata[nplot]['plottype'] == 'barplot':
            if any([i=='NA' for i in metadata[nplot]['variables']]):
                error_msg = error_msg+'\nERROR: Select exactly 2 variables for the Bar plot'
                print(error_msg)
                return {"error":error_msg}
            df = df.groupby(metadata[nplot]['variables']).size().reset_index(name="counts")
            df = df[df[metadata[nplot]['variables'][0]].notna()]

            fig = px.bar(df, x=metadata[nplot]['variables'][0], y='counts',
                         color=metadata[nplot]['variables'][1], barmode='group',
                         title="Plot of a variables: {} and {}".format(metadata[nplot]['variables'][0],
                                                                       metadata[nplot]['variables'][1])
                         )
        
            jsonPlotsDict[nplot] = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

    return jsonPlotsDict


@app.route('/clearsession', methods=['GET'])
def clearsession():
    """Clears session cookies. Useful when swithcing views from EpiVizor dashboard mode to custom build mode

    Returns:
        {string}: 'success' string upon completion
    """
    # cache.clear()
    session.clear()
    session.pop('_flashes', None)
    session['filename'] = "NA"
    print("Cleared cache and session objects")
    return 'success'


@app.route('/', methods=['GET', 'POST'])
def dashboard():
    """The main EpiVizor entrypoint function to process all frontend requests.
    On initial load the GET request is processed rendering the default template
    The user will provided an input file by clicking UPLOAD button on the front end that will trigger the POST request and the 
    request.files object will have a valid entry resulting in the generation of the global dataframe stored in the Flask Cache

    The data rendering request of the POST type will either request to render the validation screen with Flask template language,
    or render figures on unfiltered of filtered data

    This function performs data filtering based on the selected data filters available on the frontend. The values to be filtered are supplied as a 
    dictionary extracted from the request.form.to_dict() and stored in the 'datafilters2apply' key

    The observed and expected variable mapping happens by renaming the input dataframe to the expected column names using again a request.form.to_dict() 
    dictionary and the 'validatedfields_exp2obs_map' key

    Raises:
        ValueError: raises error if unsupported file extension is provided (other than xlsx and csv). This should not ever happen due to <input> tag filters

    Returns:
        html {string}:           rendered html page from the dashboard.html template
        jsonPlotsDict {dict}:    a dictionary storing figures and captions in JSON text format (usually used by AJAX requests)
        {flask.Response object}: a Flask Response Object passing a resulting CSV file (extracted dataframe) in text format for download
    """
    jsonPlotsDict = {}
    jsonPlotsDict['figures'] = {}
    jsonPlotsDict['captions'] = {}
    filter_fields2values_dict = {}
    df_column_names = []
 


    form_data_dict = request.form.to_dict()  # convert form data from frontend to a dictionary

    if form_data_dict == {}:
        clearsession() #clear any session cookies that might be left over on first page load (detected by no filters applied yet)  

    if 'datafilters2apply' in form_data_dict:
        form_data_dict['datafilters2apply'] = json.loads(form_data_dict['datafilters2apply'])
    elif 'validatedfields_exp2obs_map' in form_data_dict:
        form_data_dict['validatedfields_exp2obs_map'] = json.loads(form_data_dict['validatedfields_exp2obs_map'])

    print("Request dict form-data: {}".format(form_data_dict))

    if 'id' not in session or cache.get('df_dashboard') is None:
        session['id'] = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(10))
        session['filename'] = "NA"
  

    # render blank dashboard and validation screen if input data is specified
    if 'file' in request.files and request.method == 'POST':
        filename = request.files['file'].filename
        if filename == '':
            filename="None"
        if filename.endswith("xlsx"):
            extension="xlsx"
        elif filename.endswith("csv"):
            extension="csv"
        else:
            raise ValueError("unsupported file extension for file {}".format(filename))

        metadata_dict = uploadvalidatedata(request.files['file'], extension)
        session['filename'] = secure_filename(request.files['file'].filename)
        print("rendering splash screen after file upload to the server ...")

        if metadata_dict:      
            return render_template(
                    'dashboard.html',
                    title='Dashboard',
                    description='Dashboard for PulseNet and FoodNet Canada data visual analytics',
                    render_splash_screen = True,
                    metadata=metadata_dict,
                    method=request.method,
                    plots={},
                    session_id=session['id'],
                    file_uploaded=session['filename'],
                    filters_fields2values_dict={}

            )
        else:
            return render_template(
                    'dashboard.html',
                    title='Dashboard',
                    description='Dashboard for PulseNet and FoodNet Canada data visual analytics',
                    render_splash_screen = False,
                    metadata=metadata_dict,
                    method=request.method,
                    plots={},
                    session_id=session['id'],
                    file_uploaded=session['filename'],
                    filters_fields2values_dict={}

            )
        

    if request.method == 'POST' and isinstance(cache.get('df_dashboard'), type(pd.DataFrame())) == False: #if session expired
        print(cache.get('df_dashboard'), type(cache.get('df_dashboard')))
        print(isinstance(cache.get('df_dashboard'), type(pd.DataFrame)))
        print("Session expired and initial df is not available anymore")
        flash("Session expired and initial df is not available anymore")
        return render_template(
            'dashboard.html',
            title='Dashboard',
            description='Dashboard for PulseNet and FoodNet Canada data visual analytics',
            method = request.method,
            plots={},
            session_id="NA",
            file_uploaded="NA",
            filters_fields2values_dict={},
            render_splash_screen = False
        )

    # process POST request
    if request.method == 'POST' and (isinstance(cache.get('df_dashboard'), type(pd.DataFrame())) == True
                                     or request.form.to_dict() != {}) and cache.get("df_dashboard").empty == False:  # and session['filename'] == "NA"
        df = cache.get("df_dashboard")
        df2 = pd.DataFrame() #to hold second filtered subset data if filters applied
        print("Method POST:", isinstance(df, pd.DataFrame))
    
        ## RENAME DATAFRAME FIELDS ACCORDING 2 VALIDATION SCREEN MAPPINGS
        print("form_data_dict: {}".format(form_data_dict))
        if 'delimiter_symbol' in form_data_dict:
            session['delimiter_symbol'] = form_data_dict['delimiter_symbol']

        if 'validatedfields_exp2obs_map' in form_data_dict:
            print("Renaming dataframe according to validation screen values mapping dictionary ...")
            
            # Delete fields that were not selected in validation screen (i.e. blank selection)
            df.drop(columns=[k for k, v in form_data_dict['validatedfields_exp2obs_map'].items() if v == 'notselected'],
                    axis=1, errors='ignore', inplace=True)
            
            # rename columns based on validation fields mapping
            session['validatedfields_exp2obs_map']=form_data_dict['validatedfields_exp2obs_map']
            
            #find column indices to be renamed to account for possible duplicated column names due to conflicting variable mapping (i.e. potential name clashes)
            obs2exp_map = {v: k for k, v in form_data_dict['validatedfields_exp2obs_map'].items()}
            idx_columns2rename = [idx for idx, obs_col_name in enumerate(df.columns) if obs_col_name in obs2exp_map.keys()]
            df.rename(columns=obs2exp_map, inplace=True)
            
            # in case duplicated columns are found after column renaming append '_duplicated' to the original input data columns and generate warning
            if any(df.columns.duplicated()):
                duplicated_col_names = df.columns[df.columns.duplicated()].to_list()
                duplicated_col_indices = [idx for idx, val in enumerate(df.columns.duplicated(keep=False)) if val == True]
                duplicated_col_indices_2_rename = [idx for idx in duplicated_col_indices if idx not in idx_columns2rename] #indices of duplicated columns in original data even before column renaming

                for dupl_idx_2_rename in duplicated_col_indices_2_rename:
                    df.columns.values[dupl_idx_2_rename] = df.columns.values[dupl_idx_2_rename]+'_duplicated'

                msg='WARNING: duplicated column names (i.e. {}) found in the input data. Added _duplicated ending to the offending column(s).'.format( ",".join(duplicated_col_names))
                print(msg)
                flash(msg)    
                
            if 'hierarchical_subtype' in df.columns and 'hs_level_0' not in df.columns:
                print("Converting the hierarchical_subtype field into new hs_level_X columns in top down fashion assuming first component is level 0 (most relaxed) ")
                hier_num_of_levels = max(list(set([len(row.split(session['delimiter_symbol'])) for row in df.hierarchical_subtype if not pd.isnull(row)])))
                print("# of hierarchical levels:{}".format(hier_num_of_levels))

                hier_column_names = ["hs_level_" + str(level) for level in range(0, hier_num_of_levels)]

                if re.match(r".+\[(.+)\]",form_data_dict['validatedfields_exp2obs_map']['hierarchical_subtype']):
                    names_hs_levels = re.match(".+\[(.+)\]",form_data_dict['validatedfields_exp2obs_map']['hierarchical_subtype']
                                               ).group(1).split(',') #this is a fixed delimited assuming column_name[l1_name,l2_name,...] format
                    session['hs_names_dict']={str(i):j for i,j in enumerate(names_hs_levels)}
                    
                print("generating the new hs columns with delimiter_symbol: {}".format(session['delimiter_symbol']))
                try:
                    df[hier_column_names] = df['hierarchical_subtype'].str.split(session['delimiter_symbol'],expand=True)
                    notnull_bool_idx=df['hierarchical_subtype'].notnull()
                    df.loc[notnull_bool_idx,hier_column_names] = df.loc[notnull_bool_idx,hier_column_names].fillna('N/A')
                except Exception as e:
                    print("ERROR in hierarchial substype plot : {}".format(e))
                    flash('Hierarchial substype plot() could not split using the selected delimiter {}'.
                          format(session['delimiter_symbol']))


        df_column_names = df.columns.to_list()
        # proceed with POST if dataframe is available
        if isinstance(df, pd.DataFrame):
            df_column_names = df.columns.to_list()  # update with new appended new columns

            # CASTING field values if needed using the following positional fields in each tuple: (filter_field, df_field, dtype)
            # FORMAT: filter field in html; df_field dataframe field; dtype data type as per pandas
            field2type_cast_tuple = [('primary_type', 'primary_type', str), ('secondary_type', 'secondary_type', str),
                                     ('genetic_profile', 'genetic_profile', str),('phenotypic_profile', 'phenotypic_profile', str),
                                     ('cluster_id', 'cluster_id', str), ('investigation_id', 'investigation_id', str),
                                     ('source_type', 'source_type', str), ('source_site', 'source_site', str),
                                     ('geoloc_id', 'geoloc_id', str)]
            # convert to text hierarchical subtype field
            for column in [c for c in df.columns if re.match("hs_level_*", c)]:
                field2type_cast_tuple.append((column, column, str))
            # DATA TYPE CASTING LOOP
            for filter_field, df_field, dtype in field2type_cast_tuple:
                try:
                    if df_field in df_column_names:
                        # populate filters based on specific fields
                        filter_fields2values_dict[filter_field] = sorted(
                            set(df[df_field].fillna("not specified").astype(dtype)))
                except Exception as e:
                    print(filter_field, df_field, dtype)
                    print(e)
                    flash("Error in data conversion in the {} field;Check {};Error {}".format(df_field,
                                                                                              session['filename'], e))
                    return render_template(
                        'dashboard.html',
                        title='Dashboard',
                        description='Dashboard for PulseNet and FoodNet Canada data visual analytics',
                        plots={},
                        session_id=session['id'],
                        file_uploaded=session['filename'],
                        filters_fields2values_dict=filter_fields2values_dict,
                        render_splash_screen = False
                    )
            cache.delete('df_dashboard')
            cache.add('df_dashboard', df, timeout=0)
            print("Added dataframe to session cache with {} rows".format(df.shape[0]))


        if isinstance(df, pd.DataFrame) == False:
            return "ERROR: No data present. Upload your data file for rendering"
        
        
        # DATA FILTERS: Apply data filters submitted by the user
        # Parse filters data submitted by POST request
        # Parse multiple selections (if any) per variable
        # Filter dataframe and send it for rendering
        if 'datafilters2apply' in form_data_dict and form_data_dict['datafilters2apply'] != {}:
            print("Applying new filters to data")
            form_filt_values_dict = form_data_dict['datafilters2apply']
            print('form_filt_values_dict:{}'.format(form_filt_values_dict))

            # STARTING DATA FILTERING ON POST VALUES
            # REGEX as multiple values could be selected in filters
            # Sort keys finding which belong to which set
            filterKeysSet2 = [k for k in form_filt_values_dict if re.match(r'.+filterset2',k)]
            if filterKeysSet2:
                print("Second set of filters were selected!")
                #now need to find which variables and apply filters to a copy of the dataset
                filter_dict=extactFilterValuesFromPOST2Dict(form_filt_values_dict,'filterset2')
                print("Filter_dict Group #2: {}".format(filter_dict))
                df2 = getFilteredData(filter_dict, df.copy()) #filtered df of subset#2
                if df2.empty:
                    msg='{\"error\":\"ERROR: Empty dataframe after group #2 filter(s) application\"}'
                    print(msg)
                    return msg

            #alaways runs as set#1 is the default primary data selection. Needs to run after the set#2 data extraction due to global df reference
            filter_dict = extactFilterValuesFromPOST2Dict(form_filt_values_dict, 'filterset1')
            print("Filter_dict Group #1: {}".format(filter_dict))
            print("Starting data filtering on global data")
            df = getFilteredData(filter_dict, df.copy())
            if df.empty:
                msg='{\"error\": \"ERROR: Empty dataframe after group #1 filter(s) application\"}' #will cause AJAX call fail due to parsing
                print(msg)
                return msg

            #return only filtred data on Group #1
            if 'get_excel_subset' in form_data_dict:
                print("Return filtered csv file for data export")
                b = BytesIO()
                df.to_csv(b, sep=',', encoding='utf-8', index=False)
                b.seek(0)
                return Response(FileWrapper(b), mimetype="text/plain", direct_passthrough=True)

        # -----------------------------------RENDER PLOTS-------------------
        print("Started rendering plots on {} cases".format(df.shape))

        plot_title='Geolocation distribution ({})'.format(session['validatedfields_exp2obs_map']['geoloc_id'])
        renderHistPlot(df.copy(), 'geoloc_id', form_data_dict, jsonPlotsDict, 'geoloc_chart',
                       plot_title,
                       df2=df2.copy())

        # AGE PLOT DISTRIBUTION
        if all(item in df.columns.to_list() for item in ['age']):
            AgeSexFigCapDict = generateAgeBarPlot(df.copy(),form_data_dict,df2=df2)
            jsonPlotsDict['figures']['age_distribution_chart'] = AgeSexFigCapDict['figure']
            jsonPlotsDict['captions']['age_distribution_chart'] = AgeSexFigCapDict['caption']
        else:
            print("gender and age histogram will not be rendered. Missing age field")
            flash("gender and age histogram will not be rendered. Missing age field")
            jsonPlotsDict['figures']['age_distribution_chart'] = '{}'
            jsonPlotsDict['captions']['age_distribution_chart'] = '{}'


        plot_title='Gender distribution ({})'.format(session['validatedfields_exp2obs_map']['gender'])
        renderHistPlot(df_col_name='gender', df=df.copy(), form_data_dict=form_data_dict, jsonPlotsDict=jsonPlotsDict,
                       jsonPlotsDictKey='gender_distribution_chart',
                       plot_title=plot_title,
                       df2=df2.copy())

        plot_title='source_type distribution ({})'.format(session['validatedfields_exp2obs_map']['source_type'])
        renderHistPlot(df.copy(), 'source_type', form_data_dict, jsonPlotsDict, 'sample_source_type_distribution_chart',
                       plot_title,df2=df2.copy())

        plot_title ='Source site distribution ({})'.format(session['validatedfields_exp2obs_map']['source_site'])
        renderHistPlot(df.copy(), 'source_site', form_data_dict, jsonPlotsDict, 'sample_source_site_distribution_chart',
                       plot_title,df2=df2.copy())

        renderEpiCurve(df.copy(),'date',form_data_dict,jsonPlotsDict,'sample_accum_plot', df2=df2)

        plot_title ='Primary type ({})'.format(session['validatedfields_exp2obs_map']['primary_type'])
        renderHistPlot(df.copy(),'primary_type',form_data_dict,jsonPlotsDict,'primary_type_chart',
                       plot_title,df2=df2.copy())
        plot_title ='Secondary type ({})'.format(session['validatedfields_exp2obs_map']['secondary_type'])
        renderHistPlot(df.copy(),'secondary_type',form_data_dict,jsonPlotsDict,'secondary_type_chart',
                       plot_title,df2=df2.copy())

        # GENETIC and PHENO PROFILE PLOTS
        plot_title ='Genetic profile  ({})'.format(session['validatedfields_exp2obs_map']['genetic_profile'])
        plot_title_components ='Genetic components ({})'.format(session['validatedfields_exp2obs_map']['genetic_profile'])
        renderHistPlot(df.copy(), 'genetic_profile', form_data_dict, jsonPlotsDict, 'genetic_profile_bar_chart',
                       plot_title, df2=df2.copy(), layout_dict={'xaxis.tickangle':90})
        renderBarComponentsPlot(df.copy(), 'genetic_profile', form_data_dict, jsonPlotsDict, 'genetic_components_bar_chart',
                                plot_title_components,
                                df2=df2)

        plot_title ='Phenotypic profile  ({})'.format(session['validatedfields_exp2obs_map']['phenotypic_profile'])
        plot_title_components ='Phenotypic components ({})'.format(session['validatedfields_exp2obs_map']['phenotypic_profile'])
        renderHistPlot(df.copy(), 'phenotypic_profile', form_data_dict, jsonPlotsDict, 'phenotypic_profile_bar_chart',
                       plot_title, df2=df2.copy(), layout_dict={'xaxis.tickangle':90})
        renderBarComponentsPlot(df.copy(), 'phenotypic_profile', form_data_dict, jsonPlotsDict,
                                'phenotypic_components_bar_chart',
                                plot_title_components,
                                df2=df2)


        # Hierarchy of clusters sunburst plot
        renderSunburstPlot(df=df.copy(),jsonPlotsDict=jsonPlotsDict)
        # RENDER PRIMARY and INVESTIGATION ID BARPLOTS
        renderHistPlot(df=df.copy(), df_col_name='cluster_id', form_data_dict=form_data_dict, jsonPlotsDict=jsonPlotsDict,
                       jsonPlotsDictKey='clusterid_codes_distribution_chart',
                       plot_title='Cluster IDs distribution ({})'.format(session['validatedfields_exp2obs_map']['cluster_id']),
                       df2=df2.copy())
        renderHistPlot(df_col_name='investigation_id', df=df.copy(), form_data_dict=form_data_dict,
                       jsonPlotsDict=jsonPlotsDict,
                       jsonPlotsDictKey='investigationid_codes_distribution_chart',
                       plot_title='Investigation IDs distribution ({})'.format(session['validatedfields_exp2obs_map']['investigation_id']),
                       df2=df2.copy())

    

    #This is return for AJAX function when data selectors such as group #1, group #2 filters, groupby were applied
    if 'datafilters2apply' in request.form.to_dict() and request.method == 'POST':
        print("Sending data back to the server (only plots)")
        #filter dictionary on date filters if available
        #jsonPlotsDict['form_data_dict'] = dict((k,form_data_dict['datafilters2apply'][k]) for k in form_data_dict['datafilters2apply'].keys() if 'date' in  k)
        return jsonPlotsDict

    print("Rendring the default template on the first data load")
    
    #regular post response on the first global data load using Jinja2 templating 
    html = render_template(
        'dashboard.html',
        title='EpiVizor',
        description='EpiVizor - dashboard for PulseNet and FoodNet Canada data visual analytics',
        method = request.method,
        plots=jsonPlotsDict,
        session_id=session['id'],
        file_uploaded=session['filename'],
        filters_fields2values_dict=filter_fields2values_dict,
        df_column_names=df_column_names,
        render_splash_screen = False
    )

    print("{} method, sending data back to front end".format(request.method))
    return html


### --------------------- AUXILARY FUNCTIONS -------------------
def calculate_correlation(vector1, vector2, name):
    """Calcualte Pearson correlation using two vectors of the same length and the same variable/field

    Arguments:
        vector1 (list): list of integer values from the Group #1 dataset 
        vector2 (list): list of integer values from the Group #2 dataset
        name (string):  a custom string usually used to identify a plot that made function call

    Returns:
        (tuple):    tuple of 3 values corresponding to Pearson correlation value,two-sided p-value calculated from beta distribution 
                    and length of vector 1 values
    """
    corr, pvalue = pearsonr(vector1,vector2)
    print('Pearsons correlation in {} Group#1 vs Group #2: {}'.format(name, corr))
    return corr,pvalue, len(vector1)



def renderSunburstPlot(df,jsonPlotsDict):
    """Render sunburst plot on hierarchical data and return the resulting Plotly Figure object and caption in JSON text format.
    Since the resulting figure and caption objects are stored in global dictionary (jsonPlotsDict) this function does not return any value

    First a total number of hierchical levels are determined basd on column names with `hs_level_` prefix.
    Then given a list of hierarhical columns the unique hierarhcial paths are calculated and sorted in descending order (from highest to lowerst)
    using the pandas value_counts() and results are stored in 'df_filtered' pandas dataframe

    Only the top most abundant 100 hierchical paths are using for the plot rendering due to perfomrance considerations. Suburst are resource heavy at 
    the present Plotly library implementation v5.1.0

    If the 'hierarchical_subtype' column has the square bracked with level names supplied, this information will be added to metadata
    This column should be formated some_colum_name[name1, name2, ...]. The comma delimiter and square brackets are must components of the format

    Arguments:
        df (pandas dataframe): a copy of pandas dataframe to perform data manipulations for figure rendering
        jsonPlotsDict (dict):  a global instance of the figure and captions dictionary to store the figure and caption text objects

    """
    if 'hs_level_0' in df.columns:
            hier_column_names = [c for c in df.columns if 'hs_level_' in c]
            hier_num_of_levels = len(hier_column_names)
            print(hier_num_of_levels)
            if hier_num_of_levels == 1:
                print('Hierarchical subtype sunburst plot: Only a single hierarchical level was found! Check delimiter and input data');
                flash('Hierarchical subtype sunburst plot: Only a single hierarchical level was found! Check delimiter and input data');
            

            if all(item in df.columns.to_list() for item in hier_column_names):
                is_na_idx=df[hier_column_names].isna().apply(lambda x: not any(x), axis=1) #is True if any value is missing
                df_filtered = df[is_na_idx].value_counts(hier_column_names).reset_index(name="counts").sort_values(['counts'],ascending=False)

                if df_filtered.empty:
                    msg='Empty dataframe after filtering of missing data samples. Check data completeness.'
                    print(msg)
                    flash(msg)
                    jsonPlotsDict['figures']['hierarchy_of_clusters_sunburst_chart'] = '{}'
                    jsonPlotsDict['captions']['hierarchy_of_clusters_sunburst_chart'] = '{}'
               
                if df_filtered.shape[0] > 100:
                    display_nrows = 100
                else:
                    display_nrows = df_filtered.shape[0]


                print(f"Started rendering hierarchical subtype sunburst plot on {df_filtered.shape[0]} samples")
                plot_title ="Hierarchical subtype sunburst plot ({})".format(session['validatedfields_exp2obs_map']['hierarchical_subtype'])
                fig = px.sunburst(
                    data_frame=df_filtered.head(display_nrows),
                    path=hier_column_names,
                    values='counts',
                    hover_data=['counts'],  # generates 'customdata' field
                    maxdepth=3,
                    title=plot_title,
                    height=800
                )
                
                #adding custom data to sunburst plot figure object using a pandas dataframe. This data will be displayed upon mouseover event
                customdata = pd.DataFrame(fig["data"][0]["customdata"])
                customdata[1] = [len(i.split("/"))-1 for i in fig["data"][0]["ids"]]

                if 'hs_names_dict' in session:
                    customdata[2] = [session['hs_names_dict'][str(level)]
                                     if str(level) in session['hs_names_dict'] else "-" for level in customdata[1]]
                    howertemplate="<b>ID=%{label}</b><br>COUNT=%{customdata[0]}<br>PARENT_ID=%{parent}<br>PATH=%{id}<br>LEVEL=%{customdata[1]}<br>LEVEL_NAME=%{customdata[2]}<extra></extra>"
                else:
                    howertemplate="<b>ID=%{label}</b><br>COUNT=%{customdata[0]}<br>PARENT_ID=%{parent}<br>PATH=%{id}<br>LEVEL=%{customdata[1]}<extra></extra>"

                fig["data"][0]["customdata"] = customdata
                fig.update_traces(
                    sort=False,selector=dict(type='sunburst'),
                    hovertemplate=howertemplate)

                jsonPlotsDict['figures']['hierarchy_of_clusters_sunburst_chart'] = to_json_plotly(fig, pretty=True, engine='orjson')
                # jsonPlotsDict['hierarchy_of_clusters_sunburst_chart'] = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
                jsonPlotsDict['captions'][
                    'hierarchy_of_clusters_sunburst_chart'] = "The sunburst plot of hierarchical cluster abundances " \
                                                              "distributed across {} samples and {} total levels\n"\
                                                              "Note 1: Top-down hierarchy with the inner circle is the highest hierarchy level " \
                                                              "with the most relaxed conditions compared to other levels\n" \
                                                              "Note 2: Only {} top most numerous hierarchy paths rendered to improve performance\n" \
                                                              "Note 3: The selected delimiter symbol is '{}'\n"\
                                                              "Note 4: If defined, the Group #2 samples are NOT rendered, only Group #1 samples".format(sum(df_filtered.head(display_nrows)['counts']),hier_num_of_levels,display_nrows, session['delimiter_symbol'])
                

            else:
                flash('Hierarchal subtype  sunburst plot will not be rendered. Missing one or several {} field(s).'.format(
                    ", ".join(hier_column_names)))
                jsonPlotsDict['figures']['hierarchy_of_clusters_sunburst_chart'] = '{}'
                jsonPlotsDict['captions']['hierarchy_of_clusters_sunburst_chart'] = '{}'
    else:
        flash('Hierarchal subtype  sunburst plot will not be rendered as field not selected.')
        jsonPlotsDict['figures']['hierarchy_of_clusters_sunburst_chart'] = '{}'
        jsonPlotsDict['captions']['hierarchy_of_clusters_sunburst_chart'] = '{}'


def renderBarComponentsPlot(df, df_col_name, form_data_dict, jsonPlotsDict, jsonPlotsDictKey, plot_title,df2=pd.DataFrame()):
    """Render bar plot for the 'genetic_profile' and 'phenotypic_profile' profile fields containing individual components. 
    Given a profile field delimited by some symbol (e.g. blaCMY2|blaTEM|str), extract its components and plot using go.Bar()

    Arguments:
        df (pandas dataframe): a copy of the a dataframe to plot representing either a complete or filtred input dataset (Group #1)
        df_col_name (string):  field name to work on (either 'genetic_profile' or 'phenotypic_profile')
        form_data_dict (dict): dictionary of values submitted from fronend POST request contaning information on y-axis scale and groupy by variable
        jsonPlotsDict (dict):  a global instance of the figure and captions dictionary to store the figure and caption text objects
        jsonPlotsDictKey (string): a string identifying the plot key associated with the plot to store caption information and access figure object
                                   in the jsonPlotsDict dictionary
        plot_title (string):   a string used to assign initial plot title to the resulting figure
        df2 (pandas dataframe, optional): A copy of the Group #2 pandas dataframe representing the second dataset to render. Defaults to pd.DataFrame().
    """
    print("RenderBarComponentsPlot: Find components in the input variable {}".format(df_col_name))

    fig = make_subplots(specs=[[{"secondary_y": False}]])
    fig.update_layout(title=plot_title, xaxis_title="ID", barmode='group')
    fig.update_yaxes(title_text="counts", secondary_y=False)
    fig.update_xaxes(categoryorder="category ascending")

    if df_col_name in df.columns.to_list() and df2.empty is True:

        print("delimiter_symbol {}".format(session['delimiter_symbol']))
        plot_data_dict=Counter([item for sublist in df.loc[df[df_col_name].isnull() == False,df_col_name].str.split(session['delimiter_symbol']).to_list()
                                for item in sublist])

        if 'percent_yscale' in form_data_dict:
            fig.update_yaxes(title_text="% of trace total", secondary_y=False)
            sum_group_total =  sum(plot_data_dict.values())
            for key in plot_data_dict:
                if sum_group_total != 0:
                    plot_data_dict[key]=plot_data_dict[key]/sum_group_total*100
                else:
                    plot_data_dict[key]=0


        fig.add_trace(
            go.Bar(x=list(plot_data_dict.keys()), y=list(plot_data_dict.values()),
                   name="Group #1", showlegend=False), secondary_y=False
        )

        if 'groupby_selector_value' in form_data_dict:
            groups_total = df.groupby(
                form_data_dict['groupby_selector_value']).size().reset_index(
                name='counts').sort_values(by='counts', ascending=False)[form_data_dict['groupby_selector_value']].to_list()
            groups_total=[group for group in groups_total if not pd.isna(group)]
            groups_select = sorted([str(value) for idx,value in enumerate(groups_total) if idx < 10]) #user might provide non-string values (e.g. floats)


            if len(groups_total) > 10:
                regex_pattern="|".join(groups_select)
                df.loc[~df[form_data_dict['groupby_selector_value']].astype(str).str.fullmatch(regex_pattern),
                       form_data_dict['groupby_selector_value']]="other({})".format(len(groups_total)-len(groups_select))
                other_cat_name="other({})".format(len(groups_total)-len(groups_select))
                groups_select.append(other_cat_name)
            else:
                other_cat_name = ''




            fig = make_subplots(specs=[[{"secondary_y": False}]])
            fig.update_layout(title=plot_title, xaxis_title="ID", barmode='group')
            for idx, group in enumerate(groups_select):
                df_tmp = df[df[form_data_dict['groupby_selector_value']]==group].copy()
                df_tmp[form_data_dict['groupby_selector_value']].replace(np.nan, 'unknown', inplace=True)

                plot_data_dict=Counter([item for sublist in df_tmp.loc[df_tmp[df_col_name].isnull() == False,df_col_name].str.split(session['delimiter_symbol']).to_list()
                                    for item in sublist])

                if 'percent_yscale' in form_data_dict:
                    fig.update_yaxes(title_text="% of trace total", secondary_y=False)
                    sum_group_total = sum(plot_data_dict.values())
                    for key in plot_data_dict:
                        if sum_group_total != 0:
                            plot_data_dict[key]=plot_data_dict[key]/sum_group_total*100
                        else:
                            plot_data_dict[key]=0

                if group == other_cat_name:
                    marker_color = "#b3b3b3"
                else:
                    marker_color=px.colors.qualitative.Plotly[idx]

                fig.add_trace(
                    go.Bar(x=list(plot_data_dict.keys()), y=list(plot_data_dict.values()),
                               name=group, marker_color = marker_color, showlegend=True), secondary_y=False
                )


        jsonPlotsDict['captions'][jsonPlotsDictKey] = "The plot of \'{}\' field composed of {} components " \
                                                      "distributed across {} samples " \
                                                      "(with {} missing samples). " \
                                                      "Selected split delimiter symbol {}".format(df_col_name, len(plot_data_dict.keys()),
                                                                                          df.shape[0],
                                                                                          df[df_col_name].isna().sum(),
                                                                                          session['delimiter_symbol'])

    elif df_col_name in df.columns.to_list() and df2.empty is False:
        print("RenderBarComponentsPlot: Find components when two groups")

        plot_data_dict=Counter([item for sublist in df.loc[df[df_col_name].isnull() == False,df_col_name].str.split(session['delimiter_symbol']).to_list()
                                for item in sublist])

        if 'percent_yscale' in form_data_dict:
            fig.update_yaxes(title_text="% of trace total", secondary_y=False)
            sum_group_total =  sum(plot_data_dict.values())
            for key in plot_data_dict:
                plot_data_dict[key]=plot_data_dict[key]/sum_group_total*100

        df1_ncomponenets =  len(plot_data_dict.keys())
        fig.add_trace(
            go.Bar(x=list(plot_data_dict.keys()), y=list(plot_data_dict.values()),
                   name="Group #1", showlegend=True), secondary_y=False
        )

    
        plot_data_dict=Counter([item for sublist in df2.loc[df2[df_col_name].isnull() == False,df_col_name].str.split(session['delimiter_symbol']).to_list()
                                for item in sublist])
        if 'percent_yscale' in form_data_dict:
            sum_group_total =  sum(plot_data_dict.values())
            for key in plot_data_dict:
                plot_data_dict[key]=plot_data_dict[key]/sum_group_total*100

        df2_ncomponenets = len(plot_data_dict.keys())

        fig.add_trace(
            go.Bar(x=list(plot_data_dict.keys()), y=list(plot_data_dict.values()),
                   name="Group #2", showlegend=True), secondary_y=False
        )

        jsonPlotsDict['captions'][jsonPlotsDictKey] = "The plot of \'{}\' field component counts for the following two groups:\n" \
                                                      "a) Group #1 composed of {} components distributed across {} samples " \
                                                      "(with {} missing samples)\n" \
                                                      "b) Group #2 composed of {} components distributed across {} samples " \
                                                      "(with {} missing samples).\n" \
                                                      "Selected delimiter symbol {}".format(df_col_name, df1_ncomponenets,
                                                                                          df.shape[0], df[df_col_name].isna().sum(),
                                                                                          df2_ncomponenets, df2.shape[0],
                                                                                          df2[df_col_name].isna().sum(),
                                                                                          session['delimiter_symbol'])

        unique_categories=sorted(set(fig.data[1].x).union(fig.data[0].x))
        group1_counts = [fig.data[0].y[fig.data[0].x.index(date)] if date in fig.data[0].x else 0  for date in unique_categories]
        group2_counts = [fig.data[1].y[fig.data[1].x.index(date)] if date in fig.data[1].x else 0  for date in unique_categories ]
        if len(group1_counts) >=3 and len(group2_counts)>=3 :
            corr, pvalue, npoints = calculate_correlation(group1_counts,group2_counts, 'epicurve')
            jsonPlotsDict['captions'][jsonPlotsDictKey]=jsonPlotsDict['captions'][jsonPlotsDictKey]+ \
                                                        "\nPearson correlation coefficient between two groups based on the {} data points: {:.3f} (p-value: {:.3e})".format(
                                                            npoints,corr,pvalue)

    fig.for_each_trace(
        lambda trace: trace.update(visible='legendonly') if trace.name == "unknown" else ()
    )

    if 'log_yscale' in form_data_dict:
        fig.update_yaxes(type='log', title='counts')
    else:
        fig.update_yaxes(type='linear')

    fig.update_layout(
        {"xaxis":{"categoryorder":'category ascending'}},
        updatemenus=[
            dict(
                buttons=list([
                    dict(
                        args=[
                            {'visible': True, 'xaxis.categoryorder': 'category ascending'}
                        ],
                        label="alphabetical",
                        method="relayout"
                    ),
                    dict(
                        args=[
                            {'visible': True, 'xaxis.categoryorder': 'category descending'}
                        ],
                        label="reverse alphabetical",
                        method="relayout"
                    ),
                    dict(
                        args=[
                            {'visible': True, 'xaxis.categoryorder': 'total descending'}
                        ],
                        label="descending",
                        method="relayout"
                    ),
                    dict(
                        args=[
                            {'visible': True, 'xaxis.categoryorder': 'total ascending'}
                        ],
                        label="ascending",
                        method="relayout"
                    )
                ]),
                direction="down",
                active=0,
                pad={"r": 0,"l":0, "t": -10,"b":0},
                showactive=True,
                x=1,
                xanchor="right",
                y=1.1,
                yanchor="top"
            )
        ]
    )

    jsonPlotsDict['figures'][jsonPlotsDictKey] = to_json_plotly(fig, pretty=False, engine='orjson')

    if df_col_name not in df.columns.to_list():
        flash('Barplot would not be rendered on {}.'.format(df_col_name))
        jsonPlotsDict['figures'][jsonPlotsDictKey] = '{}'
        jsonPlotsDict['captions'][jsonPlotsDictKey] = '{}'




def renderHistPlot(df, df_col_name, form_data_dict, jsonPlotsDict, jsonPlotsDictKey, plot_title, df2=pd.DataFrame(), layout_dict={}):
    """Render a historgram plot on categorical variables. This is the most frequently used function to plot rendering 
    Given a column name by 'df_col_name' and input dataset stored in 'df' render a plot via px.histogram() Plotly function

    Arguments:
        df (pandas dataframe): a copy of the a dataframe to plot representing either a complete or filtred input dataset (Group #1)
        df_col_name (string):  a field name existing in the 'df' dataframe to work on (e.g. 'geoloc_id', 'primary_type')
        form_data_dict (dict): a dictionary of values submitted from fronend POST request contaning information on y-axis scale and groupy by variable
        jsonPlotsDict (dict):  a global instance of the figure and captions dictionary to store the figure and caption text objects
        jsonPlotsDictKey (string): a string identifying the plot key associated with the plot to store caption information and access figure object
                                   in the jsonPlotsDict dictionary
        plot_title (string):   a string used to assign initial plot title to the resulting figure
        df2 (pandas dataframe, optional): A copy of the Group #2 pandas dataframe representing the second dataset to create traces on
        layout_dict (dict, optional): A dictionary of with Plotly Layout directives such as forcing vertical x-axis tick labels {'xaxis.tickangle':90}. Defaults to {}.
    """
    print("renderHistPlot '{}': df1 shape {}; df2 shape: {}".format(df_col_name, df.shape, df2.shape))
    if df_col_name in df.columns.to_list() and df2.empty is True:
        print("{} abundances barplot being rendered ...".format(df_col_name))

        if any(not element for element in df[df_col_name].isna()):
            # standardize the filed names in case they are long or have non-informative information (e.g. empty antigenic formula)
            df.loc[df[df_col_name] == 0, df_col_name] = 'unknown'
            df.loc[df[df_col_name] == '-:-:-', df_col_name] = 'unknown'
            df.fillna('unknown',inplace=True)
            n_unknown = sum(df[df_col_name] == 'unknown')
            #n_unknown = df[df_col_name].isna().sum()
            
            if 'groupby_selector_value' in form_data_dict:
                print("renderHistPlot() group by mode on value: {}".format(form_data_dict['groupby_selector_value']))
                
                if any(df[form_data_dict['groupby_selector_value']].isna()):
                    df[form_data_dict['groupby_selector_value']].replace(np.nan, 'unknown', inplace=True)

                groups_total = df[~df.isin(['unknown'])].groupby(
                    form_data_dict['groupby_selector_value']).size().reset_index(
                    name='counts').sort_values(by='counts', ascending=False)[form_data_dict['groupby_selector_value']].to_list()
                #print(groups_total)
                #groups_total = [g for g in groups_total if g != 'unknown']
                groups_select = sorted([re.sub(r'\.','\\.',str(value))for idx,value in enumerate(groups_total) if idx < 10]) #user might provide non-string values (e.g. floats)

                

                if len(groups_total) > 10:
                    regex_pattern = "|".join(groups_select)
                    print(regex_pattern)
                    df.loc[~df[form_data_dict['groupby_selector_value']].astype(str).str.fullmatch(regex_pattern),
                       form_data_dict['groupby_selector_value']]='other({})'.format(len(groups_total)-len(groups_select))


                #print(form_data_dict)
                if 'percent_yscale' in form_data_dict:
                    print("Percent scale selected")
                    fig = px.histogram(df, x=df_col_name,
                                       title=plot_title,
                                       color=form_data_dict['groupby_selector_value'],
                                       height=600,
                                       histnorm='percent')
                    fig.layout['yaxis']['title']='% of trace total'
                    fig.update_layout({'barmode':'group'})
                    fig.update_yaxes(type='linear')
                    print("Done")
                else:
                    fig = px.histogram(df,
                                       x=df_col_name, color=form_data_dict['groupby_selector_value'],
                                       title=plot_title,
                                       height=600)
                    fig.update_layout(barmode='group')
                    if 'log_yscale' in form_data_dict:
                        fig.update_yaxes(type='log', title = 'counts')
                    else:
                        fig.update_yaxes(type='linear')

                fig.data=[fig.data[idx] for idx in np.argsort([i.name for i in fig.data])] #order alphabetically
                for idx,trace in enumerate(fig.data):
                    #print(idx,trace.name, len(px.colors.qualitative.Plotly))
                    if idx >= len(px.colors.qualitative.Plotly)-1: #there are 10 colours, so if idx is greater repeat again colours
                        idx = idx%len(px.colors.qualitative.Plotly)
                    if trace.name == "unknown":
                        trace.update(visible='legendonly')
                        trace.marker.color= "#FF0000"
                    elif 'other' in trace.name:
                        trace.marker.color="#b3b3b3"
                    else:
                        trace.marker.color= px.colors.qualitative.Plotly[idx]
            else:
                if 'percent_yscale' in form_data_dict:
                    fig = px.histogram(df, x=df_col_name,
                                       title=plot_title,
                                       height=600,
                                       histnorm='percent')
                    fig.update_yaxes(title_text="% of trace total", secondary_y=False, type='linear')
                else:
                    fig = px.histogram(df, x=df_col_name,
                                       title=plot_title,
                                       height=600)
                    if 'log_yscale' in form_data_dict:
                        fig.update_yaxes(title_text="counts",secondary_y=False, type='log')
                    else:
                        fig.update_yaxes(title_text="counts", secondary_y=False, type='linear')

            fig.update_layout(
                {"xaxis":{"categoryorder":'category ascending'}},
                updatemenus=[
                    dict(
                        buttons=list([
                            dict(
                                args=[
                                    {'visible': True, 'xaxis.categoryorder': 'category ascending'}
                                ],
                                label="alphabetical",
                                method="relayout"
                            ),
                            dict(
                                args=[
                                    {'visible': True, 'xaxis.categoryorder': 'category descending'}
                                ],
                                label="reverse alphabetical",
                                method="relayout"
                            ),
                            dict(
                                args=[
                                    {'visible': True, 'xaxis.categoryorder': 'total descending'}
                                ],
                                label="descending",
                                method="relayout"
                            ),
                            dict(
                                args=[
                                    {'visible': True, 'xaxis.categoryorder': 'total ascending'}
                                ],
                                label="ascending",
                                method="relayout"
                            )
                        ]),
                        direction="down",
                        active=0,
                        pad={"r": 0,"l":0, "t": -10,"b":0},
                        showactive=True,
                        x=1,
                        xanchor="right",
                        y=1.1,
                        yanchor="top"
                    )
                ]
            )
            if n_unknown != 0:
                fig.update_layout(showlegend=True)

            fig.update_layout(layout_dict)
            graphJSON = to_json_plotly(fig.update_layout(xaxis_title="ID", xaxis={'type': 'category'}), pretty=False,
                                       engine='orjson')

            jsonPlotsDict['figures'][jsonPlotsDictKey] = graphJSON
            jsonPlotsDict['captions'][jsonPlotsDictKey] = "The plot of \'{}\' field composed of {} categories " \
                                                          "distributed across {} samples (with {} missing samples).".format(
                df_col_name,
                df[df[df_col_name].isna() == False][df_col_name].unique().size,
                df.shape[0],
                df[df[df_col_name].isna() == True].shape[0]+n_unknown)
        else:
            print("{} has no valid values to build bar plot on".format(df_col_name))
            flash('Barplot would not be rendered on {}.'.format(df_col_name))
            jsonPlotsDict['figures'][jsonPlotsDictKey] = '{}'
            jsonPlotsDict['captions'][jsonPlotsDictKey] = '{}'
    elif df_col_name in df.columns.to_list() and df2.empty is False:
        print("Two groups case ...")
        df.loc[df[df_col_name] == 0, df_col_name] = 'unknown'
        df.loc[df[df_col_name] == '-:-:-', df_col_name] = 'unknown'
        df.fillna('unknown',inplace=True)

        n_unknown = sum(df[df_col_name] == 'unknown')
        df2.loc[df2[df_col_name] == 0, df_col_name] = 'unknown'
        df2.loc[df2[df_col_name] == '-:-:-', df_col_name] = 'unknown'
        df2.fillna('unknown',inplace=True)
        n_unknown2 = sum(df2[df_col_name] == 'unknown')

        fig=make_subplots(specs=[[{"secondary_y": False}]])
        fig.update_layout(title=plot_title, xaxis_title="ID",barmode='group', xaxis={'type': 'category'})

        if 'percent_yscale' in form_data_dict:
            fig.add_trace(
                go.Histogram(x=df[df_col_name],
                             name="Group #1", histnorm='percent',
                             showlegend=True)
            )
            fig.add_trace(
                go.Histogram(x=df2[df_col_name],
                             histnorm='percent',
                             name="Group #2", showlegend=True)
            )
            fig.update_yaxes(title_text="% of trace total", secondary_y=False, type='linear')
        else:
            print('Adding traces')
            fig.add_trace(
                go.Histogram(x=df[df_col_name],
                       name="Group #1", showlegend=True)
            )
            fig.add_trace(
                go.Histogram(x=df2[df_col_name],
                             name="Group #2", showlegend=True)
            )
            if 'log_yscale' in form_data_dict:
                fig.update_yaxes(title_text="counts",secondary_y=False, type='log')
            else:
                fig.update_yaxes(title_text="counts", secondary_y=False, type='linear')


        fig.update_layout(
            {"xaxis":{"categoryorder":'category ascending'}},
            updatemenus=[
                dict(
                    buttons=list([
                        dict(
                            args=[
                                {'visible': True, 'xaxis.categoryorder': 'category ascending'}
                            ],
                            label="alphabetical",
                            method="relayout"
                        ),
                        dict(
                            args=[
                                {'visible': True, 'xaxis.categoryorder': 'category descending'}
                            ],
                            label="reverse alphabetical",
                            method="relayout"
                        ),
                        dict(
                            args=[
                                {'visible': True, 'xaxis.categoryorder': 'total descending'}
                            ],
                            label="descending",
                            method="relayout"
                        ),
                        dict(
                            args=[
                                {'visible': True, 'xaxis.categoryorder': 'total ascending'}
                            ],
                            label="ascending",
                            method="relayout"
                        )
                    ]),
                    direction="down",
                    active=0,
                    pad={"r": 0,"l":0, "t": -10,"b":0},
                    showactive=True,
                    x=1,
                    xanchor="left",
                    y=1.2,
                    yanchor="top"
                )
            ]
        )

        graphJSON = to_json_plotly(fig, pretty=False,
                                   engine='orjson')

        jsonPlotsDict['figures'][jsonPlotsDictKey] = graphJSON
        jsonPlotsDict['captions'][jsonPlotsDictKey] = "The plot of \'{}\' field composed of two groups:\na) Group #1 with {} categories " \
                                                      "distributed across {} samples (with {} missing samples);\n" \
                                                      "b) Group #2 with {} categories distributed across {} samples (with {} missing samples).".format(
            df_col_name,
            df[df[df_col_name].isna() == False][df_col_name].unique().size,
            df.shape[0],
            df[df[df_col_name].isna() == True].shape[0]+n_unknown,
            df2[df2[df_col_name].isna() == False][df_col_name].unique().size,
            df2.shape[0]+n_unknown2,
            df2[df2[df_col_name].isna() == True].shape[0]
        )
        fig.update_layout(layout_dict)

        print("Pearson correlation coefficient calculation ")
        unique_categories=[i for i in set(fig.data[0].x).union(fig.data[1].x) if i != None] #remove note defined None category
        group1_counts_dict = Counter(fig.data[0].x)
        group1_counts= [group1_counts_dict[key_profile] for key_profile in unique_categories]
        group2_counts_dict = Counter(fig.data[1].x)
        group2_counts= [group2_counts_dict[key_profile] for key_profile in unique_categories]

        if len(group1_counts) >=3 and len(group2_counts)>=3 :
            corr, pvalue, npoints = calculate_correlation(group1_counts,group2_counts, df_col_name)
            jsonPlotsDict['captions'][jsonPlotsDictKey]=jsonPlotsDict['captions'][jsonPlotsDictKey]+\
                                                    "\nPearson correlation coefficient between two groups based on the {} data points: {:.3f} (p-value: {:.3e})".format(
            npoints,corr,pvalue)
        else:
            jsonPlotsDict['captions'][jsonPlotsDictKey] = '{}'
        print("Done rendering")
    else:
        flash('Barplot would not be rendered on {}.'.format(df_col_name))
        jsonPlotsDict['figures'][jsonPlotsDictKey] = '{}'
        jsonPlotsDict['captions'][jsonPlotsDictKey] = '{}'

def renderEpiCurve(df, x_time_var, form_data_dict, jsonPlotsDict, jsonPlotsDictKey, df2=pd.DataFrame()):
    """Render an epidemiological curve based on a selected time-series variable (e.g. collection date).
    Create Day, Week, Month and Year views by carefully transforming data


    Arguments:
        df (pandas dataframe): a copy of the a dataframe to plot representing either a complete or filtred input dataset (Group #1)
        x_time_var (string): a variable containing the full date (day, month, year) that could be parsed by pandas (e.g. 2021-03-01)
        form_data_dict (dict): a dictionary of values submitted from fronend POST request contaning information on y-axis scale and groupy by variable
        jsonPlotsDict (dict): a global instance of the figure and captions dictionary to store the figure and caption text objects
        jsonPlotsDictKey (string): a string identifying the plot key associated with the plot to store caption information and access figure object
                                   in the jsonPlotsDict dictionary
        df2 (pandas dataframe, optional): A copy of the Group #2 pandas dataframe representing the second dataset to create traces on. Defaults to pd.DataFrame().

    Returns:
        ValueError: raises a value error if 'x_time_var' variable is not defined or filtred dataframe is empty due to missing data or corresponding column does not exist in data
    """
    # EPIDEMIOLOGICAL CURVE
    dropdown_plot_type_dict=dict(
        buttons=list([
            dict(
                args=[
                    {'visible': True, 'type': 'bar', 'mode': 'markers+lines'}
                ],
                label="bar",
                method="restyle"
            ),
            dict(
                args=[{'visible': True, 'type': 'scatter', 'mode': 'markers+lines'}],
                label="line",
                method="restyle"
            )
        ]),
        direction="down",
        active=0,
        pad={"r": 0,"l":0, "t": -10,"b":0},
        showactive=True,
        x=1,
        xanchor="right",
        y=1.1,
        yanchor="top"
    )

    if x_time_var not in df.columns.to_list():
        msg="Epidemiological plot not rendered as {} field is missing in input".format(x_time_var)
        print(msg); flash(msg); 
        jsonPlotsDict['figures'][jsonPlotsDictKey] = '{}'
        jsonPlotsDict['captions'][jsonPlotsDictKey] = '{}'
        return ValueError("Epidemiological plot not rendered as {} field is missing in input".format(x_time_var))

    if any(not element for element in df[x_time_var].isna()):
        print("Rendering an epidemiological curve ..")

        fig = make_subplots(specs=[[{"secondary_y": False}]])
        fig.update_layout(title="Epidemiological curve", xaxis_title="Day",
                          barmode='stack', legend={'traceorder':'normal'}
                          ) #initial plot to be shown

        df[x_time_var]=pd.to_datetime(df[x_time_var],errors='coerce') #convert to date
        idx_date_ok = pd.to_datetime(df['date'], errors='coerce').notnull()
        if False in idx_date_ok.value_counts():
            df1_n_missing = idx_date_ok.value_counts()[False]
        else:
            df1_n_missing=0
        

        df_filtered = df.loc[idx_date_ok].groupby(
            pd.Grouper(key=x_time_var, axis=0, freq='W-MON')).size().reset_index(name="counts")

        if df_filtered.empty:
            return ValueError('Empty datetime dataframe on {}'.format(x_time_var))

        df_filtered["week"] = df_filtered[x_time_var].dt.isocalendar().week
        df_filtered["day"] = df_filtered[x_time_var].dt.day
        df_filtered["month"] = df_filtered[x_time_var].dt.month
        df_filtered["year"] = df_filtered[x_time_var].dt.year
        df_filtered.loc[df_filtered.eval(
            "day==31 & month==12"), "week"] = 53  # as ISO will assing week 1 to December 31st dates
        data_x_week_year = [str(y) + "/0" + str(w) if w < 10 else str(y) + "/" + str(w)  for y in
                            range(min(df_filtered["year"]), max(df_filtered["year"] + 1))
                            for w in range(1, 53 + 1)] #addition to zero to week values < 10 guarantees correct name sorting
        data_x_month_year = [str(y) + "/" + str(m) for y in
                             range(min(df_filtered["year"]), max(df_filtered["year"] + 1)) for m in
                             range(1, 12 + 1)]
        data_x_year = [str(y) for y in range(min(df_filtered["year"]), max(df_filtered["year"] + 1))]

        if 'groupby_selector_value' in form_data_dict:
            fig.update_layout(legend_title_text=form_data_dict['groupby_selector_value'])
            fig.layout['yaxis']['title']='count'
            df_filtered = df.loc[idx_date_ok]
            group_plot_vals_dict={}
            group_plot_vals_dict['daily']={'x':[],'y':[]}
            group_plot_vals_dict['weekly']={'x':[],'y':[]}
            group_plot_vals_dict['monthly']={'x':[],'y':[]}
            group_plot_vals_dict['yearly']={'x':[],'y':[]}

            # get top 9 sub-categories and the rest lump into others category
            groups_total = df.groupby(
                form_data_dict['groupby_selector_value']).size().reset_index(
                name='counts').sort_values(by='counts', ascending=False)[form_data_dict['groupby_selector_value']].to_list()
            groups_select = sorted([value for idx,value in enumerate(groups_total) if idx < 10])
            if len(groups_total) > 10:
                n_other_categories = len(groups_total)-len(groups_select)
                groups_select.append('other({})'.format(n_other_categories))


            groups_select_df_index = []
            other_group_idx = None #other category index for grey color setting
            for group_idx, group in enumerate(groups_select):
                print("Processing groupby sub-category: {}".format(groups_select[group_idx]))
                if re.search(r'other',group): #last index
                    df_tmp=df_filtered.loc[~df_filtered.index.isin(set(groups_select_df_index))].groupby(
                        pd.Grouper(key=x_time_var, axis=0, freq='W-MON')).size().reset_index(name="counts") #get complement of indices (the remainder not captured in groups)
                    other_group_idx=group_idx
                else:
                    df_tmp = df_filtered.loc[df_filtered[form_data_dict['groupby_selector_value']] == group].groupby(
                        pd.Grouper(key=x_time_var, axis=0, freq='W-MON')).size().reset_index(name="counts")
                    groups_select_df_index = groups_select_df_index + df_tmp.index.to_list()

                df_tmp["week"] = df_tmp[x_time_var].dt.isocalendar().week
                df_tmp["day"] = df_tmp[x_time_var].dt.day
                df_tmp["month"] = df_tmp[x_time_var].dt.month
                df_tmp["year"] = df_tmp[x_time_var].dt.year

                if 'percent_yscale' in form_data_dict:
                    sum_total=sum(df_tmp["counts"])
                    group_plot_vals_dict['daily']['y'].append([i/sum_total*100 for i in df_tmp["counts"].to_list()])
                    group_plot_vals_dict['daily']['x'].append(df_tmp[x_time_var])
                else:
                    group_plot_vals_dict['daily']['x'].append(df_tmp[x_time_var])
                    group_plot_vals_dict['daily']['y'].append(df_tmp["counts"])


                fig.add_trace(
                    go.Bar(x=group_plot_vals_dict['daily']['x'][group_idx], y=group_plot_vals_dict['daily']['y'][group_idx],
                           name=group, showlegend=True), secondary_y=False
                )

                if other_group_idx:
                    fig.data[other_group_idx].update({"marker":{"color":"#b3b3b3"}}) #grey color reserved for other category
                #hide missing data trace by default
                fig.for_each_trace(
                    lambda trace: trace.update(visible='legendonly') if trace.name == "unknown" else ()
                )

                data_y_month_year = [0] * len(data_x_month_year)
                for idx, item in enumerate(data_x_month_year):
                    y, m = [int(i) for i in item.split('/')]
                    # result_df = df_filtered.query("month == "+m+" &  year == "+y)
                    result_df = df_tmp.loc[(df_tmp["month"] == m) & (df_tmp["year"] == y)]
                    if result_df.empty == False:
                        data_y_month_year[idx] = sum(result_df["counts"])

                group_plot_vals_dict['monthly']['x']=data_x_month_year
                group_plot_vals_dict['monthly']['y'].append(data_y_month_year)


                data_y_week_year = [0] * len(data_x_week_year)
                for idx, item in enumerate(data_x_week_year):
                    y, w = [int(i) for i in item.split('/')]
                    result_df = df_tmp.loc[(df_tmp["week"] == w) & (df_tmp["year"] == y)]
                    if result_df.empty == False:
                        data_y_week_year[idx] = sum(result_df["counts"])

                group_plot_vals_dict['weekly']['x']=data_x_week_year
                group_plot_vals_dict['weekly']['y'].append(data_y_week_year)

                data_y_year = [0] * len(data_x_year)
                for idx, y in enumerate(data_x_year):
                    result_df = df_tmp.loc[df_tmp["year"] == int(y)]
                    if result_df.empty == False:
                        data_y_year[idx] = sum(result_df["counts"])
                group_plot_vals_dict['yearly']['x']=data_x_year
                group_plot_vals_dict['yearly']['y'].append(data_y_year)

                if 'percent_yscale' in form_data_dict:
                    sum_total=sum(group_plot_vals_dict['weekly']['y'][group_idx])
                    group_plot_vals_dict['weekly']['y'][group_idx]=[i/sum_total*100 for i in group_plot_vals_dict['weekly']['y'][group_idx]]
                    sum_total=sum(group_plot_vals_dict['monthly']['y'][group_idx])
                    group_plot_vals_dict['monthly']['y'][group_idx]=[i/sum_total*100 for i in group_plot_vals_dict['monthly']['y'][group_idx]]
                    sum_total=sum(group_plot_vals_dict['yearly']['y'][group_idx])
                    group_plot_vals_dict['yearly']['y'][group_idx]=[i/sum_total*100 for i in group_plot_vals_dict['yearly']['y'][group_idx]]
                    fig.layout['yaxis']['title']='% of trace total'


            fig.update_layout(
                updatemenus=[
                    dict(
                        type="buttons",
                        direction="right",
                        buttons=list([
                            dict(
                                args=[
                                    {'visible': True,
                                     'type': 'bar',
                                     'y': group_plot_vals_dict['daily']['y'],
                                     'x': group_plot_vals_dict['daily']['x']
                                     },
                                    {'title': 'Epidemiological curve (Daily)',
                                     'yaxis.title': fig.layout.yaxis.title.text, 'xaxis.title': "Date",
                                     'showlegend': True}
                                ],
                                label="Daily",
                                method="update"
                            ),
                            dict(
                                args=[
                                    {'visible': True,
                                     'type': 'bar',
                                     'y': group_plot_vals_dict['weekly']['y'],
                                     'x': [group_plot_vals_dict['weekly']['x']]
                                     }, {'title': 'Epidemiological curve (Weekly)',
                                         'yaxis.title': fig.layout.yaxis.title.text, 'xaxis.title': "Week starting on",
                                         'showlegend': True}
                                ],
                                label="Week",
                                method="update"
                            ),
                            dict(
                                args=[
                                    {'visible': True,
                                     'type': 'bar',
                                     'y': group_plot_vals_dict['monthly']['y'],
                                     'x': [group_plot_vals_dict['monthly']['x']]
                                     }, {'title': 'Epidemiological curve (Montly)',
                                         'yaxis.title': fig.layout.yaxis.title.text, 'xaxis.title': "Month",
                                         'showlegend': True}
                                ],
                                label="Montly",
                                method="update"
                            ),
                            dict(
                                args=[
                                    {'visible': True,
                                     'type': 'bar',
                                     'y': group_plot_vals_dict['yearly']['y'],
                                     'x': [group_plot_vals_dict['yearly']['x']]
                                     }, {'title': 'Epidemiological curve (Yearly)',
                                         'yaxis.title': fig.layout.yaxis.title.text, 'xaxis.title': "Year",
                                         'showlegend': True}
                                ],
                                label="Yearly",
                                method="update"
                            )
                        ]),
                        active=0,
                        yanchor="top",
                        pad={"r": 0,"l":0, "t": -10,"b":0},
                        xanchor="right",
                        x=0.6,
                        y=1.13,
                        showactive=True
                    ),
                    dropdown_plot_type_dict
                ]
            )



            if 'log_yscale' in form_data_dict:
                fig.update_yaxes(type='log', title='counts')
            else:
                fig.update_yaxes(type='linear')

            jsonPlotsDict['figures'][jsonPlotsDictKey] = to_json_plotly(fig, pretty=False, engine='orjson')
            jsonPlotsDict['captions'][jsonPlotsDictKey] = "Absolute and cummulative weekly cases " \
                                                             "per year plot on {} samples with information on " \
                                                             "\'{}\' variable ({} unknown).".format(
                df.loc[idx_date_ok].shape[0],
                x_time_var,
                df[x_time_var].isna().sum())
            return 0 #finish function execution as group by has finished processing

        data_y_week_year = [0] * len(data_x_week_year)

        for idx, item in enumerate(data_x_week_year):
            y, w = [int(i) for i in item.split('/')]
            result_df = df_filtered.loc[(df_filtered["week"] == w) & (df_filtered["year"] == y)]
            if result_df.empty == False:
                data_y_week_year[idx] = sum(result_df["counts"])


        data_y_month_year = [0] * len(data_x_month_year)

        for idx, item in enumerate(data_x_month_year):
            y, m = [int(i) for i in item.split('/')]
            # result_df = df_filtered.query("month == "+m+" &  year == "+y)
            result_df = df_filtered.loc[(df_filtered["month"] == m) & (df_filtered["year"] == y)]
            if result_df.empty == False:
                data_y_month_year[idx] = sum(result_df["counts"])


        data_y_year = [0] * len(data_x_year)

        for idx, y in enumerate(data_x_year):
            # result_df = df_filtered.query("month == "+m+" &  year == "+y)
            result_df = df_filtered.loc[df_filtered["year"] == int(y)]
            if result_df.empty == False:
                data_y_year[idx] = sum(result_df["counts"])


        # create graph objects from pre-calculated data
        fig = make_subplots(specs=[[{"secondary_y": False}]])
        fig.update_layout(title="Epidemiological curve", xaxis_title="Day", barmode='group') #initial plot to be shown
        fig.update_yaxes(title_text="counts", secondary_y=False)

        if 'percent_yscale' in form_data_dict:
            sum_total=sum(df_filtered['counts'].to_list())
            df_filtered['counts']=[i/sum_total*100 for i in df_filtered['counts'].to_list()]
            sum_total=sum(data_y_week_year)
            data_y_week_year=[i/sum_total*100 for i in data_y_week_year]
            sum_total=sum(data_y_month_year)
            data_y_month_year=[i/sum_total*100 for i in data_y_month_year]
            sum_total=sum(data_y_year)
            data_y_year=[i/sum_total*100 for i in data_y_year]
            fig.layout['yaxis']['title']='% of trace total'


        fig.add_trace(
            go.Bar(x=df_filtered[x_time_var], y=df_filtered["counts"],
                   name="Group #1", showlegend=True), secondary_y=False
        )


        fig.update_layout({'showlegend': False})  # Turn off legend if only single group or subset

        fig.update_layout(
            updatemenus=[
                dict(
                    type="buttons",
                    direction="right",
                    buttons=list([
                        dict(
                            args=[
                                {'visible': [True],
                                 'type': 'bar',
                                 'y': [df_filtered["counts"]],
                                 'x': [df_filtered[x_time_var]]
                                 },
                                {'title': 'Epidemiological curve (Daily)',
                                 'yaxis.title': fig.layout.yaxis.title.text,
                                 'xaxis.title': "Day", 'showlegend': False}
                            ],
                            label="Daily",
                            method="update"
                        ),
                        dict(
                            args=[
                                {'visible': [True],
                                 'type': 'bar',
                                 'y': [data_y_week_year],
                                 'x': [data_x_week_year]
                                 }, {'title': 'Epidemiological curve (Weekly)',
                                     'yaxis.title': fig.layout.yaxis.title.text,
                                     'xaxis.title': "Week starting",
                                     'xaxis.categoryorder':'category ascending',
                                     'showlegend': False}
                            ],
                            label="Weekly",
                            method="update"
                        ),
                        dict(
                            args=[
                                {'visible': [True],
                                 'type': 'bar',
                                 'y': [data_y_month_year],
                                 'x': [data_x_month_year]
                                 }, {'title': 'Epidemiological curve (Monthly)',
                                     'yaxis.title': fig.layout.yaxis.title.text, 'xaxis.title': "Month",
                                     'showlegend': False}
                            ],
                            label="Monthly",
                            method="update"
                        ),
                        dict(
                            args=[
                                {'visible': [True],
                                 'type': 'bar',
                                 'y': [data_y_year],
                                 'x': [data_x_year]
                                 }, {'title': 'Epidemiological curve (Yearly)',
                                     'yaxis.title': fig.layout.yaxis.title.text, 'xaxis.title': "Year",
                                     'showlegend': False}
                            ],
                            label="Yearly",
                            method="update"
                        )
                    ]),
                    active=0,
                    yanchor="top",
                    x=0.6,
                    y=1.13,
                    showactive=True
                ),
                dropdown_plot_type_dict

            ]
        )
        jsonPlotsDict['captions'][jsonPlotsDictKey] = "Sample counts per time unit (day, week, month or year) " \
                                                         "on {} samples with available information" \
                                                         "(and {} samples with unknown time information).".format(
            sum(idx_date_ok),
            df1_n_missing
        )
        # if group#2 are selected the second subset rendering
        if df2.empty is False:
            fig.update_layout({'showlegend': True})
            df2[x_time_var]=pd.to_datetime(df2[x_time_var],errors='coerce') #convert to date
            idx_date_ok_df2 = pd.to_datetime(df2['date'], errors='coerce').notnull()
            if False in idx_date_ok_df2.value_counts():
                df2_n_missing = idx_date_ok.value_counts()[False]
            else:
                df2_n_missing=0
            df2_filtered = df2.loc[idx_date_ok_df2].groupby(
                pd.Grouper(key=x_time_var, axis=0, freq='W-MON')).size().reset_index(name="counts")
            df2_filtered["week"] = df2_filtered[x_time_var].dt.isocalendar().week
            df2_filtered["day"] = df2_filtered[x_time_var].dt.day
            df2_filtered["month"] = df2_filtered[x_time_var].dt.month
            df2_filtered["year"] = df2_filtered[x_time_var].dt.year
            df2_filtered.loc[df2_filtered.eval(
                "day==31 & month==12"), "week"] = 53  # as ISO will assing week 1 to December 31st dates
            data2_x_week_year = [str(y) + "/0" + str(w) if w<10 else str(y) + "/" + str(w) for y in
                                range(min(df2_filtered["year"]), max(df2_filtered["year"] + 1))
                                for w in range(1, 53 + 1)]
            data2_x_month_year = [str(y) + "/" + str(m) for y in
                             range(min(df2_filtered["year"]), max(df2_filtered["year"] + 1)) for m in
                             range(1, 12 + 1)]
            data2_x_year = [str(y) for y in range(min(df2_filtered["year"]), max(df2_filtered["year"] + 1))]

            data2_y_week_year = [0] * len(data2_x_week_year)
            for idx, item in enumerate(data2_x_week_year):
                y, w = [int(i) for i in item.split('/')]
                # result_df = df_filtered.query("week == "+w+" &  year == "+y)
                result_df = df2_filtered.loc[(df2_filtered["week"] == w) & (df2_filtered["year"] == y)]
                if result_df.empty == False:
                    data2_y_week_year[idx] = sum(result_df["counts"])

            data2_y_month_year = [0] * len(data2_x_month_year)
            for idx, item in enumerate(data2_x_month_year):
                y, m = [int(i) for i in item.split('/')]
                # result_df = df_filtered.query("month == "+m+" &  year == "+y)
                result_df = df2_filtered.loc[(df2_filtered["month"] == m) & (df2_filtered["year"] == y)]
                if result_df.empty == False:
                    data2_y_month_year[idx] = sum(result_df["counts"])

            data2_y_year = [0] * len(data2_x_year)
            for idx, y in enumerate(data2_x_year):
                # result_df = df_filtered.query("month == "+m+" &  year == "+y)
                result_df = df2_filtered.loc[df2_filtered["year"] == int(y)]
                if result_df.empty == False:
                    data2_y_year[idx] = sum(result_df["counts"])

            if 'percent_yscale' in form_data_dict:
                fig.layout.yaxis.title.text = '% of trace total'
                sum_total=sum(df2_filtered['counts'].to_list())
                df2_filtered['counts']=[i/sum_total*100 for i in df2_filtered['counts'].to_list()]
                sum_total=sum(data2_y_week_year)
                data2_y_week_year=[i/sum_total*100 for i in data2_y_week_year]
                sum_total=sum(data_y_month_year)
                data2_y_month_year=[i/sum_total*100 for i in data2_y_month_year]
                sum_total=sum(data2_y_year)
                data2_y_year=[i/sum_total*100 for i in data2_y_year]

            fig.add_trace(
                go.Bar(x=df2_filtered[x_time_var], y=df2_filtered["counts"],
                       name="Group #2", showlegend=True), secondary_y=False
            )

            fig.update_layout(
                updatemenus=[
                    dict(
                        type="buttons",
                        direction="right",
                        buttons=list([
                            dict(
                                args=[
                                    {'visible': [True],
                                     'type': 'bar',
                                     'y': [df_filtered["counts"],df2_filtered["counts"]],
                                     'x': [df_filtered[x_time_var], df2_filtered[x_time_var]]
                                     },
                                    {'title': 'Epidemiological curve (Daily)',
                                     'yaxis.title': fig.layout.yaxis.title.text,
                                     'xaxis.title': "Day",
                                     'xaxis.categoryorder':'category ascending',
                                     'showlegend': True}
                                ],
                                label="Daily",
                                method="update"
                            ),
                            dict(
                                args=[
                                    {'visible': [True],
                                     'type': 'bar',
                                     'y': [data_y_week_year, data2_y_week_year],
                                     'x': [data_x_week_year, data2_x_week_year]
                                     }, {'title': 'Epidemiological curve (Weekly)',
                                         'yaxis.title': fig.layout.yaxis.title.text,
                                         'xaxis.title': "Week starting",
                                         'xaxis.categoryorder':'category ascending',
                                         'showlegend': True}
                                ],
                                label="Weekly",
                                method="update"
                            ),
                            dict(
                                args=[
                                    {'visible': [True],
                                     'type': 'bar',
                                     'y': [data_y_month_year,data2_y_month_year],
                                     'x': [data_x_month_year, data2_x_month_year]
                                     }, {'title': 'Epidemiological curve (Monthly)',
                                         'yaxis.title': fig.layout.yaxis.title.text, 'xaxis.title': "Month",
                                         'xaxis.categoryorder':'category ascending',
                                         'showlegend': True}
                                ],
                                label="Monthly",
                                method="update"
                            ),
                            dict(
                                args=[
                                    {'visible': [True],
                                     'type': 'bar',
                                     'y': [data_y_year,data2_y_year],
                                     'x': [data_x_year, data2_x_year]
                                     }, {'title': 'Epidemiological curve (Yearly)',
                                         'xaxis.categoryorder':'category ascending',
                                         'yaxis.title': fig.layout.yaxis.title.text,
                                         'xaxis.title': "Year",
                                         'showlegend': True}
                                ],
                                label="Yearly",
                                method="update"
                            )
                        ]),
                        active=0,
                        yanchor="top",
                        x=0.6,
                        y=1.13,
                        showactive=True
                    ),
                    dropdown_plot_type_dict
                ]
            )
            jsonPlotsDict['captions'][jsonPlotsDictKey] = "Sample counts per time unit (day, week, month or year) " \
                                                             "on two groups:\na) Group 1 composed of {} samples with information " \
                                                             "(and {} samples with unknown time information).\n" \
                                                             "b) Group 2 composed of {} samples with information (and {} samples with unknown time information) ".format(
                sum(idx_date_ok),
                df1_n_missing,
                sum(idx_date_ok_df2),
                df2_n_missing

            )
            unique_categories=sorted(set(fig.data[1].x).union(fig.data[0].x))
            
            if isinstance(fig.data[0].x, tuple):
                group1_counts = [fig.data[0].y[fig.data[0].x.index(date)] if date in fig.data[0].x else 0  for date in unique_categories ]
                group2_counts = [fig.data[1].y[fig.data[1].x.index(date)] if date in fig.data[1].x else 0  for date in unique_categories ]
            else:     
                group1_counts = [fig.data[0].y[np.where(fig.data[0].x == date)[0][0]] if date in fig.data[0].x else 0  for date in unique_categories]
                group2_counts = [fig.data[1].y[np.where(fig.data[1].x == date)[0][0]] if date in fig.data[1].x else 0  for date in unique_categories ]

            
            if len(group1_counts) >=3 and len(group2_counts)>=3 :
                corr, pvalue, npoints = calculate_correlation(group1_counts,group2_counts, 'epicurve')
                jsonPlotsDict['captions'][jsonPlotsDictKey]=jsonPlotsDict['captions'][jsonPlotsDictKey]+ \
                                                        "\nPearson correlation coefficient between two groups based on the {} data points: {:.3f} (p-value: {:.3e})".format(
                                                            npoints,corr,pvalue)

        if 'log_yscale' in form_data_dict:
            fig.update_yaxes(type='log', title='counts')
        else:
            fig.update_yaxes(type='linear')

        fig.update_layout(barmode='group', xaxis={'categoryorder':'category ascending'})
        print("Rendering drop down view menu")
        jsonPlotsDict['figures'][jsonPlotsDictKey] = to_json_plotly(fig, pretty=False, engine='orjson')
        with open('epicurve_test.html','w') as fp:
            fp.writelines(plotly.io.to_html(fig, include_plotlyjs='cdn',default_width='100%', default_height='100%'))
    else:
        print("Epidemiological plot not rendered due to no data in {} field (all values are missing)".format(x_time_var))
        jsonPlotsDict['figures'][jsonPlotsDictKey] = '{}'
        jsonPlotsDict['captions'][jsonPlotsDictKey] = '{}'

def uploadvalidatedata(file, extension):
    """Starts loading input CSV or Excel file to webapp cache and into pandas dataframe object for future data manipulations
    To speed loading the openpyxl is used to more rapidly upload and parse Excel files. 
    The CSV files are read much faster than Excel file due to minimal parsing and conversion steps

    Also generates metadata dictionary to be displayed in validation screen including list of observed variable names (i.e. columns),
    data dimensions, missing counts per variable, expected variables tip text displayed over blue information icon. 
    Finally calculates missing values percentage for each variable

    Arguments:
        file (FileStorage): the actual file transferred from the frontend and stored in Flask FileStorage object
        extension (string): extracted file extension from the submitted file

    Raises:
        ValueError: raises error if uploaded file is of not allowed type (other than CSV and EXLS). 
        Due <input> field parameters filtering the input files, this error should not happen

    Returns:
        metadata_dict {dict}: a dictionary of metadata information on uploaded file to be rendered by the validation variables screen post file upload
    """
    print("Uploadvalidatedata()")
    metadata_dict = {}

    start_time = time.time()
    #both cases allow for duplicated columns (no automatic renaming)
    if extension == "xlsx":
        data = load_workbook(file, read_only=True, data_only=True).active.values
        cols = next(data)
        df = pd.DataFrame(data, columns=cols) 
    elif extension == "csv":
        df = pd.read_csv(file, header = None, skiprows = 1)
        file.seek(0)
        rownames  =  pd.read_csv(file, header = None, nrows = 1).loc[0,:].to_list()
        df.columns = rownames
    else:
        raise ValueError("Unknown input file extension. Only xlsx and csv supported")
    end_time = time.time()
    print("Input data loading time {}s".format(end_time-start_time) )
    print("Checkin data on duplicated entries ... ")
    if df.columns.duplicated().any():
        dupl_col_names = ",".join(df.columns[df.columns.duplicated()].to_list())
        print(f"Duplicated columns found! Duplicated column(s) name(s): {dupl_col_names}")
        flash(f"Duplicated column(s) found ({dupl_col_names}) in file {file.filename}! Aborting upload. Make sure input has unique header names")
        return {}
    #    df=df.loc[:,df.columns.duplicated()==False].copy()
    
    print("Empty rows cleaning")
    df=df[df.iloc[:,0].isna()==False].copy()
    print(f"Total valid data rows in input {df.shape[0]}")


    cache.delete('df_dashboard') #delete previous data
    cache.add('df_dashboard', df, timeout=0)

    metadata_dict['data_shape'] = df.shape
    metadata_dict['fields_observed'] = df.columns.sort_values().unique().to_list() #+ ['']
    metadata_dict['fields_counts_observed'] = dict(zip(metadata_dict['fields_observed'],
                                                       [df[field].count() for field in
                                                        metadata_dict['fields_observed']]))
    
    metadata_dict['fields_counts_unique_observed'] = dict(zip(df.columns.sort_values().to_list(),
                                                              [df[field].unique().size for field in metadata_dict['fields_counts_observed'].keys()]))
    metadata_dict['fields_counts_missing_observed'] = dict(zip(df.columns.sort_values().to_list(),
                                                               [metadata_dict['data_shape'][0] -
                                                                metadata_dict['fields_counts_observed'][field]
                                                                for field in metadata_dict['fields_counts_observed']]))
    metadata_dict['fields_types_expected'] = {'sample_id': 'unique identifier', 'hierarchical_subtype': 'hierarchical list',
                                              'date': 'date (YYYY-MM-DD)',
                                              'cluster_id': 'categorical', 'investigation_id': 'categorical',
                                              'age': 'positive float', 'gender': 'categorical',
                                              'primary_type': 'categorical', 'secondary_type': 'categorical',
                                              'source_site': 'categorical', 'geoloc_id': 'categorical', 'source_type': 'categorical',
                                              'genetic_profile': 'list', 'phenotypic_profile': 'list',
                                              }
    metadata_dict['fields_types_expected_group_filters_avail'] = {
                                              'sample_id': 'No', 'hierarchical_subtype': 'Yes',
                                              'date': 'Yes',
                                              'cluster_id': 'Yes', 'investigation_id': 'Yes',
                                              'age': 'No', 'gender': 'No',
                                              'primary_type': 'Yes', 'secondary_type': 'Yes',
                                              'source_site': 'Yes', 'geoloc_id': 'Yes', 'source_type': 'Yes',
                                              'genetic_profile': 'Yes', 'phenotypic_profile': 'Yes',
                                              }
    metadata_dict['fields_types_expected_info'] = { 'sample_id': 'unique sample identifier. No duplicates are allowed',
                                                    'hierarchical_subtype': 'hierarchical subtype field with values arranged in a top-down path. \
                                                        That is from the highest (i.e. most relaxed) to the lowest (i.e. most stringent) hierarchy level separated by a delimiter symbol such as pipe.\
                                                             E.g., 2340|3711|4110|4616 with 2340 being the cluster identifier at the highest level',
                                                    'date': 'The date a given sample was collected, isolated, submitted, etc. This field is used to generate an epidemilogical curve',
                                                    'cluster_id': 'cluster identifier field. This could be an internal lab identifer, etc.',
                                                    'investigation_id': 'similar to cluster_id field, allows to define a second set of identifiers such as epidemilogical cluster or external second identifier',
                                                    'age': 'sample age in any numerical format. Integers and floats are supported',
                                                    'gender': 'sampe gender (e.g. male, female, etc.)',
                                                    'primary_type': 'primary type categorical field (e.g. species name, serotype)',
                                                    'secondary_type': 'secondary type categorical field usually at higher resolution (e.g., serovar, antigen)',
                                                    'source_site': 'a categocial field that could be used to define isolation site or tissue (e.g., body fluid, organ, etc.)',
                                                    'geoloc_id': 'a geolocation categorical field allowing to define geography (e.g., country, province, city, etc.)',
                                                    'source_type': 'a categorical field allowing to characterize isolation source such as human and non-human, etc.',
                                                    'genetic_profile': 'a categorical composite field related to genetic sample profile composition defined by one or more components separated by the | pipe symbol. E.g., AMR genes present such as fosA|str',
                                                    'phenotypic_profile': 'a categorical composite field related to phenotypic characteristics defined by one or more components \
                                                        separated by the selected delimiter symbol. E.g., AMR phenotypes encoded as streptomycin_susceptible|betalactam_resistant',
                                              }
    metadata_dict['fieldtypes_observed'] = dict(zip(df.columns.sort_values().to_list(),
                                                    [str(df.dtypes[field]) for field in
                                                     metadata_dict['fields_counts_observed']]))
    metadata_dict['warnings'] = dict.fromkeys(metadata_dict['fields_observed'], '')

    # find missing observed missing fieldnames
    for field_obs in metadata_dict['fields_observed']:
        if field_obs in metadata_dict['fields_types_expected'] and metadata_dict['fields_counts_missing_observed'][
            field_obs]:

            print(field_obs,metadata_dict['fields_counts_missing_observed'][field_obs],metadata_dict['fields_counts_observed'][field_obs])
            percent_missing=round(
                metadata_dict['fields_counts_missing_observed'][field_obs] / metadata_dict['fields_counts_observed'][
                    field_obs]*100, 3)
            if percent_missing == 0:
                percent_missing_str = "<0.001"
            else:
                percent_missing_str = str(percent_missing)
            metadata_dict['warnings'][field_obs] = percent_missing_str + '% missing values'
       
    return metadata_dict


def generateAgeBarPlot(df, form_data_dict, df2=pd.DataFrame()):
    """Generates age distribution bar plot by binning age into 5 year bins. Calculates counts per each age bin. 
    Provides bar or line views of the plot for easier comparioson of data groups. Returns a dictionary of Plotly figure in JSON format and figure caption text

    Arguments:
        df (pandas dataframe): a copy of dataframe to render plot on usually represents either a total or filtred data assigned to Group #1
        form_data_dict (dict): a dictionary of values submitted from fronend POST request contaning information on y-axis scale and groupy by variable
        df2 (pandas dataframe, optional): a . Defaults to pd.DataFrame().

    Returns:
        {dict}: a dictionary containing the 'figure' and 'captions' keys that store JSON representation of Plotly figure object and figure caption text
    """
    print("Generating age distribution plot ...")

    # df_global = cache.get('df_dashboard') #unfiltred
    df_barplot_dict = {'group1': {},'group2':{}}
    df_barplot_dict['group1']['xaxis'] = {}
    df_barplot_dict['group1']['yaxis'] = {}
    df_barplot_dict['group2']['xaxis'] = {}
    df_barplot_dict['group2']['yaxis'] = {}

    plot_title="Age distribution ({})".format(session['validatedfields_exp2obs_map']['age'])
    # print(df_global.shape, df.shape)
    layout = go.Layout(
        title=plot_title,
        barmode="group",
        bargroupgap=0,
        bargap=0.1,
        yaxis=dict(title='counts', fixedrange=True, rangemode='tozero'),
        xaxis={'tickangle': -90, 'type':'category','title':'Age Bins'},
        margin={'autoexpand': True, 'b': 50, 't': 50},
        #legend=dict(orientation='h', borderwidth=1, y=-0.2, x=0.6)
    )

    try:
        df.loc[:,'age']=pd.to_numeric(df.loc[:,'age'], errors='coerce')
        df_filtered = df[~df["age"].isna()].copy()
        df_filtered['age_bin'] = pd.cut(df_filtered['age'], [x for x in range(0, 110, 5)], right=False)
        df_filtered_counts = df_filtered.groupby(["age_bin"]).size().reset_index(name='counts')
        age_bins_str = ["[" + str(i.left) + "-" + str(i.right) + ")" for i in df_filtered_counts["age_bin"]]
        df_barplot_dict['group1']['xaxis'] = age_bins_str
        df_barplot_dict['group1']['yaxis'] = df_filtered_counts["counts"].to_list()
        if df2.empty == False:
            print("Two groups defined, working on df2 {}".format(df2.shape))
            df2['age']=pd.to_numeric(df2['age'], errors='coerce')
            df2_filtered = df2[~df2["age"].isna()]
            df2_filtered['age_bin'] = pd.cut(df2_filtered['age'], [x for x in range(0, 110, 5)], right=False)
            df2_filtered_counts = df2_filtered.groupby(["age_bin"]).size().reset_index(name='counts')
            df_barplot_dict['group2']['yaxis'] = df2_filtered_counts["counts"].to_list()
            df_barplot_dict['group2']['xaxis'] = df_barplot_dict['group1']['xaxis']
    except Exception as e:
        print(e)
        print("Age field could not be converted to integer. The age distribution plot could not be rendered")
        flash("Age field could not be converted to integer. The age distribution plot could not be rendered")
        return ({'figure': '{}',
                 'caption': '{}'
                 })


    plot_objs_list = []
    # if GROUP BY is activated or not
    if 'groupby_selector_value' in form_data_dict:
        layout['legend']['title']=form_data_dict['groupby_selector_value']
        offset_counter=0

        groups_total = df.groupby(
            form_data_dict['groupby_selector_value']).size().reset_index(
            name='counts').sort_values(by='counts', ascending=False)[form_data_dict['groupby_selector_value']].to_list()
        groups_select = sorted([str(value) for idx,value in enumerate(groups_total) if idx < 10]) #user might provide non-string values (e.g. floats)


        if len(groups_total) > 10:
            other_cat_name="other({})".format(len(groups_total)-len(groups_select))
            regex_pattern="|".join(groups_select)
            df_filtered.loc[~df_filtered[form_data_dict['groupby_selector_value']].astype(str).str.fullmatch(regex_pattern),
                       form_data_dict['groupby_selector_value']]=other_cat_name
            groups_select.append(other_cat_name)
        else:
            other_cat_name = ''

        for idx,group in enumerate(groups_select):
            df_filtered_counts = df_filtered[df_filtered[form_data_dict['groupby_selector_value']] == group].groupby(["age_bin"]).size().reset_index(name='counts')
            df_barplot_dict['group1']['yaxis'] = df_filtered_counts["counts"].to_list()
            if 'percent_yscale' in form_data_dict:
                total_sum=sum(df_barplot_dict['group1']['yaxis'])

                if total_sum > 0:
                    df_barplot_dict['group1']['yaxis']=[i/total_sum*100 for i in df_barplot_dict['group1']['yaxis']]

                layout['yaxis']['title']='% of trace total'

            if group == other_cat_name:
                marker_color = "#b3b3b3"
            else:
                marker_color = px.colors.qualitative.Plotly[idx]

            plot_objs_list.append(
                go.Bar(name=group,
                       x=df_barplot_dict['group1']['xaxis'],
                       y=df_barplot_dict['group1']['yaxis'],
                       offsetgroup=offset_counter,
                       marker_color=marker_color
                       )
            )
            offset_counter=offset_counter+1


        figCaption = "Age distribution plot on {} " \
                     "cases in groupby mode with age data ({} cases age unknown)".format(df_filtered.shape[0],
                                                                         df.shape[0] - df_filtered.shape[0])
    elif df2.empty is False:
        if 'percent_yscale' in form_data_dict:
            total_sum=sum(df_barplot_dict['group1']['yaxis'])
            total_sum2=sum(df_barplot_dict['group2']['yaxis'])
            df_barplot_dict['group1']['yaxis']=[i/total_sum*100 for i in df_barplot_dict['group1']['yaxis']]
            df_barplot_dict['group2']['yaxis']=[i/total_sum2*100 for i in df_barplot_dict['group2']['yaxis']]
            #layout['yaxis']['range']=[0,1]
            layout['yaxis']['title']='% of trace total'
        plot_objs_list = [
            go.Bar(name="Group #1",
                   x=df_barplot_dict['group1']['xaxis'],
                   y=df_barplot_dict['group1']['yaxis'],
                   offsetgroup=0,
                   marker_color='#636efa'  #5467F6
                   ),
            go.Bar(name="Group #2",
                   x=df_barplot_dict['group2']['xaxis'],
                   y=df_barplot_dict['group2']['yaxis'],
                   offsetgroup=1,
                   marker_color='#EF553B'
                   )
        ]
        figCaption = "Age distribution plot on two groups:\n" \
                     "a) Group #1 composed of {} cases with age data ({} cases with age unknown)\n" \
                     "b) Group #2 composed of {} cases with age data ({} cases with age unknown)".format(
            df_filtered.shape[0],df.shape[0] - df_filtered.shape[0],df2_filtered.shape[0],df.shape[0] - df2_filtered.shape[0] )
    else:
        if 'percent_yscale' in form_data_dict:
            total_sum=sum(df_barplot_dict['group1']['yaxis'])
            df_barplot_dict['group1']['yaxis']=[i/total_sum*100 for i in df_barplot_dict['group1']['yaxis']]
            #layout['yaxis']['range']=[0,1]
            layout['yaxis']['title']='% of trace total'
        plot_objs_list = [
            go.Bar(name="Group #1",
                   x=df_barplot_dict['group1']['xaxis'],
                   y=df_barplot_dict['group1']['yaxis'],
                   offsetgroup=0,
                   marker_color="#636efa"
                   )
        ]
        figCaption = "Age distribution plot on {} " \
                     "cases with age data ({} cases age unknown)".format(df_filtered.shape[0],
                                                                         df.shape[0] - df_filtered.shape[0])


    fig = go.Figure(
        data=plot_objs_list,
        layout=layout
    )

    if len(plot_objs_list) == 2:
        corr, pvalue, npoints = calculate_correlation(fig['data'][0]['y'],fig['data'][1]['y'], "age")
        figCaption=figCaption+"\nPeason correlation between two groups based on the {} data points: {:.3f} (p-value: {:.3e})".format(
            npoints,corr,pvalue)
        print('Pearsons correlation in \"age\" Group#1 vs Group #2 {}'.format(corr))
    #fig.data=[fig.data[idx] for idx in np.argsort([i.name for i in fig.data])] #order traces alphabetically

    fig.for_each_trace(
        lambda trace: trace.update(visible='legendonly') if trace.name == "unknown" else (),
    )

    if 'log_yscale' in form_data_dict:
        fig.update_yaxes(type='log', title='counts')
    else:
        fig.update_yaxes(type='linear')

    # buttons to switch plots
    fig.update_layout(
        updatemenus=[
            dict(
                type="buttons",
                direction="right",
                buttons=list([
                    dict(
                        args=[
                            {'visible': True, 'type': 'scatter', 'mode': 'markers+lines'},
                            {'yaxis.title': fig.layout.yaxis.title.text}
                        ],
                        label="Line",
                        method="update"
                    ),
                    dict(
                        args=[{
                            'visible': True,
                            'type': 'bar',
                            'base': [j.base if j.base != None else 0 for i, j in enumerate(fig.data)]
                        },
                            {'yaxis.title': fig.layout.yaxis.title.text}
                        ],
                        label="Bar",
                        method="update"
                    )
                ]),
                active=1,
                yanchor="top",
                showactive=True,
                y=1.11,
                x=0.55
            ),
        ]
    )

    graphJSON = to_json_plotly(fig, pretty=False, engine='orjson')
    return ({'figure': graphJSON,
             'caption': figCaption})


