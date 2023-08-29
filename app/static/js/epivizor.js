/**
     * Opens the file upload dialog box by clicking on a hidden file selector button `Choose File` of the <input> with the 'file_selector' id
     * Also removes the the file upload info message 'UPLOAD DATA TO RENDER (xlsx or csv)'
     */
 function openFileUploadDialog() {
    document.getElementById('file_selector').click();
}

/**
 * Updates file upload progress bar with the current upload value reported as a percentage for total
 * @param {Object} event -  XMLHttpRequest progress event triggered when data is received by the server
 */
function progressHandler(event) {
    //console.log(event)
    var percent = (event.loaded / event.total) * 100;
    $(".progressUploadBar")[1].value= Math.round(percent);

}

/**
 * Updates the plot title customize dropdown of the PLOT CONTROLS section by iterating over the rendered plots objects
 * and populationing the dropdown plot titles
 */
function updatePlotTitlesSection() {
    console.log('Running updatePlotTitlesSection() to update plot titles selector')
    document.querySelectorAll('.plot-container').forEach( (element, index) => {
        //console.log(element.parentElement.id)
        var option = document.createElement("option");
        option.value = element.parentElement.id;
        option.text=document.querySelectorAll('.plot-container .gtitle')[index].textContent
        document.getElementById('plot_title_selectpicker').add(option)
    })
    $(".selectpicker#plot_title_selectpicker").selectpicker('refresh')
}

/**
 * Update tab titles text based on the <button> name attribute value having 'P#' where # is the plot sequencial number 
 * starting from 1
 */
function updateTabTitlesSection(){
    console.log('Running updateTabTitlesSection()')
    Array.from(document.getElementsByClassName('tablink')).forEach((button)=>{
        //console.log(button.textContent)
        var option = document.createElement("option");
        option.value = button.name;
        option.text = button.textContent;
        document.getElementById('tab_title_selectpicker').add(option)
    })
    $(".selectpicker#tab_title_selectpicker").selectpicker('refresh')

}

/**
 * Update Plotly plot title based on the user input entered in the <input id='tab_title_input_field'> field
 * The dropdown with <select id='tab_title_selectpicker'> determines which plot to update
 * @param {String} newTitle - Custom user title entered in the input field  
 */
function updateTabTitle(newTitle){
    var indexTabNameField = document.getElementById('tab_title_selectpicker').value
    Array.from(document.getElementsByClassName('tablink')).forEach((tabElement) =>{
            if(tabElement.name === indexTabNameField){tabElement.textContent=newTitle}
        }

    )
}

/**
 * Update the number of visible levels of the Sunburst plot after user changes the slider value. 
 * By default the 3 hierarchical levels are visible.
 * The function obtains the value of the <input id="sunburst_max_levels_slider"> tag representing the number of visible levels and
 * then runs Plotly.restyle() using that value resulting in plot update
 */
function updateSunburstVisibleLevels(){
    var set_level_val = document.getElementById('sunburst_max_levels_slider').value
    if(document.getElementById('plotDiv_hierarchy_of_clusters_sunburst_chart') !== null) {
        Plotly.restyle('plotDiv_hierarchy_of_clusters_sunburst_chart', {"maxdepth": set_level_val})
        console.log('updateSunburstVisibleLevels() with '+String(set_level_val))
    }else{
        console.log('No element with ID plotDiv_hierarchy_of_clusters_sunburst_chart available at this time. Skip current hs level update')
    }
}

/**
 * Update the hierarchical maximum level upper bound of the slider control based on the sunburst plot metadata stored in the 
 * customdata dataframe 2nd column. Since level data on hierarchical paths is stores in descending order, the first element provides
 * information on the maximum number of levels. 
 */
function updateSunburstMaxLevels(){
    if (document.getElementById('plotDiv_hierarchy_of_clusters_sunburst_chart') !== null ) {
        var max_levels = document.getElementById('plotDiv_hierarchy_of_clusters_sunburst_chart').data[0].customdata[0][1] + 1
        document.getElementById('sunburst_max_levels_slider').setAttribute('max', max_levels)
        console.log('updateSunburstMaxLevels():' + String(max_levels))
    }else{
        document.getElementById('sunburst_max_levels_slider').setAttribute('disabled','')
        document.querySelector('#sunburst_max_levels_panel span').textContent=1
    }
}

/**
 * Render initial trace controls panel html code allowing to change trace name and color as its contents
 * depends on the selected data traces by the user (Group #1 and #2 or GROUP BY traces).
 * The function takes the first plot and extract current color and trace names
 */
function renderTraceControls(){
    console.log('renderTraceControls()');
    let elements = document.querySelectorAll(`div[class^="js-plotly-plot"]`)
    if(elements.length > 0) {
        let trace_names2colors={}
        let element = elements[0]
        let index_colorway=0
        console.log(element.id+':'+element.data[0].name);
        element.data.forEach((subcategory, index) => {
                if (index >= 10){
                    index_colorway=index-9*Math.trunc(index/9)-1
                }else{index_colorway = index} //total 10 colors, restart color index (repeat color)

                if(subcategory.name.length !== 0) {
                    if ('marker' in subcategory) {
                        trace_names2colors[subcategory.name] = subcategory.marker.color
                    } else { //single trace
                        trace_names2colors[subcategory.name] = element.layout.template.layout.colorway[index_colorway] //not all single trace plots have marker info. Default to blue
                    }
                }else{
                    trace_names2colors['Group #'+(index+1)] = element.layout.template.layout.colorway[index_colorway]
                }
            });

        console.log(trace_names2colors)
        if(trace_names2colors.lenght !== 0){$('#trace_names_colors').css({'display': 'block'})} //turn on the traces control block}

        //generate color picker controls in a panel based on the trace_name -> color
        $('#trace_controls').remove() //remove previous controls if they exist
        const element_div = document.createElement("div");
        element_div.id = 'trace_controls';
        element_div.style="display:grid;grid-template-columns: repeat(2, 1fr);gap: 2px;align-items:center; grid-auto-columns: min-content"
        let index=0
        for (const [trace_name, color]of Object.entries(trace_names2colors)) {
            console.log("trace_names2colors:"+trace_name+":"+color+":"+index);
            let element_input = document.createElement("input"); element_input.style="margin-left:auto";
            element_input.type="color"; element_input.setAttribute("value",color);
            element_input.setAttribute("name",index);
            element_input.setAttribute("onchange","updatePlotAttr(this)")

            let element_trace_name = document.createElement("input");
            element_trace_name.type="text";element_trace_name.style="background-color: whitesmoke"//element_label.for='trace_color_1';
            element_trace_name.setAttribute("name",index);
            element_trace_name.setAttribute("value",trace_name); element_trace_name.setAttribute("placeholder",'Trace name')
            element_trace_name.setAttribute("class",'form-control')
            element_trace_name.setAttribute("onchange","updatePlotAttr(this)")

            element_div.appendChild(element_trace_name); element_div.appendChild(element_input)
            index=index+1;

        }
        document.getElementById('trace_names_colors_list').appendChild(element_div)
    }


}

/**
 * Reset all previosuly selected data filters and render the initial input data (i.e. global unfiltered dataset)
 * The function resets group #1 and #2 and GROUP BY filters together with the y-axis transformation sliders (% and log scales)
 * Finishes with a POST request for plots re-calculation via the key postPlotData()
 */
function resetAllFilters(){
    console.log("Resetting all filters ...")
    let groupby_values_array=$('#groupby_selector').selectpicker('option:selected').val(); //need multiple=true to get array
    let filters_group1_values=Array.from($("#accordion_section_filters_subset1").find("select")).map(i=>{return(i.value)}).filter(function(i){return i.length > 0})
    let filters_group2_values=Array.from($("#accordion_section_filters_subset2").find("select")).map(i=>{return(i.value)}).filter(function(i){return i.length > 0})

    if(filters_group1_values.length > 0) {
        console.log('Resetting group#1 filters due groupby selector activation')
        let select_tags1 = $("#accordion_section_filters_subset1").find("select");
        for (let i = 0; i < select_tags1.length; i++) {
            $('#' + select_tags1[i].id).selectpicker('val', null);
        }

    }
    $("#date_range_filter1").find("input")[0].value=''; $("#date_range_filter1").find("input")[1].value=''

    if(filters_group2_values.length > 0) {
        console.log('Resetting group#2 filters due groupby selector activation')
        let select_tags2 = $("#accordion_section_filters_subset2").find("select");
        for (let i = 0; i < select_tags2.length; i++) {
            $('#' + select_tags2[i].id).selectpicker('val', null);
        }

    }
    $("#date_range_filter2").find("input")[0].value=''; $("#date_range_filter2").find("input")[1].value=''
    //reset groupby filter
    if (groupby_values_array.length > 0){
        $('#groupby_selector').selectpicker('val',null);

    }
    $('#percent_scale_toggle')[0].checked=false; $('#log_scale_toggle')[0].checked=false;

    document.getElementById("settings_selected_groupby").innerHTML='-';
    document.getElementById("settings_selected_group1").innerHTML='-';
    document.getElementById("settings_selected_group2").innerHTML='-';

    alert("Reset all data filters")
    if (document.querySelectorAll(`div[class^="js-plotly-plot"]`).length >0) {
        postPlotData()
    }
}

/** 
 * Update color, trace name or plot title submitted via the PLOT CONTROLS pannel controls
 * @param {Object} obj - The <input> DOM object containing information on picked colour by the user or new trace name 
 * @returns - 0 if plot title successfully updated
 */
function updatePlotAttr(obj){
    console.log("updatePlotAttr function(): color hex value "+obj.value+" trace idx:"+obj.name)
    const graphDivs = document.querySelectorAll(`div[class^="js-plotly-plot"]`);

    //update plot title and exit the function
    if(obj.id === "plot_title_input_field") {
        Plotly.relayout(document.getElementById('plot_title_selectpicker').value, {'title': obj.value})
        alert("Plot title changed to '"+obj.value+"'")
        return 0
    }

    //find which trace to update color or trace name by getting index from name attribute
    let trace_idx=obj.name //input tags are given index names to be able to refer to them after trace name change
    console.log(obj.value+":"+trace_idx)
    graphDivs.forEach(function(graphDiv){
        if(graphDiv.data.length-1 >= trace_idx) { //skip a plot which does not have the required trace index such as sunburst
            if(obj.type === "color") {
                Plotly.restyle(graphDiv, {'marker.color': obj.value}, trace_idx);
            }else if(obj.type === "text"){
                console.log('Update trace name:'+obj.value)
                Plotly.restyle(graphDiv, {'name': [obj.value], 'showlegend':true}, trace_idx);
                Plotly.relayout(graphDiv, {'showlegend':true});
            }else{
                console.log("uknown input type "+obj.type+" (expected text or color). not graph updates")
            }

        }
    })
}

/**
 * Generate HTML standalone plots snapshot page that can be shared and interacted with by just opening the resulting html page
 * This function does not make any backend calls making it very fast and easy to capture the current view state preserving all view properties (color, titles, captions, etc)
 * The function goes over each Plotly Graph object and extracts data and layout fields that are then coverted to JSON string
 * The user upon resulting html file openning will trigger the Plotly.newPlot() functions with all necessary data and re-create these objects
 */
function saveweb2html() {
    const date = new Date();
    let downloadLink = document.createElement("a");
    downloadLink.download = 'epivizor_view_snapshot_'+date.getDate()+'-'+
        (date.getMonth()+1)+'-'+date.getFullYear()+'_'+date.getHours()+'h_'+date.getMinutes()+'min.html';

    var plotDiv_ids = Array.from(document.querySelectorAll(".js-plotly-plot")).map( (element)=>{return element.id} )
    var stringHtmlTobeSaved = '<script src="https://cdn.plot.ly/plotly-2.2.0.min.js"></script>\n';
    for (const id of plotDiv_ids){  
        stringHtmlTobeSaved+='<div id='+id+' class="plotly-graph-div" style="height:100%; width:100%;"></div>\n'
        stringHtmlTobeSaved+="\n"+document.querySelector('#'+id+' p').outerHTML+"\n"
    } 
    stringHtmlTobeSaved+='<script type="text/javascript">\n'
    for (const id of plotDiv_ids){ 
        var plotObj = document.getElementById(id)
        plotObj.layout.height=0; plotObj.layout.width=0; //to remove size limits of the plot in the resulting html    
        stringHtmlTobeSaved+='\nPlotly.newPlot("'+id+'", \n'+
        JSON.stringify(plotObj.data)+',\n'+JSON.stringify(plotObj.layout)+');'
    }    
    stringHtmlTobeSaved+='</script>'
    
    const textToBLOB = new Blob([stringHtmlTobeSaved], { type: 'text/html;charset=utf-8' });
    downloadLink.href = window.URL.createObjectURL(textToBLOB);
    downloadLink.click(); //Trigger a click on the element
}

/**
 * Generates a new window of static plots preview to be then printed or stored as a PDF file via the system print dialog box
 * Dynamically generates the preview window window by iterating over the plot divs and calling the Plotly.toImage() function returning Promise objects
 * The await directive waits until plots are transformed to SVG images preserving quality.
 */
async function saveweb2pdf(){ 
   const date = new Date();
   var printHtml = window.open('', 'PrintWindow', '_top');
   var paramsSession = document.querySelectorAll('.settings_selected_grid span')
   var pageHtml = '<head><title>print preview</title><head>'
   pageHtml += '<div style="text-align:center"><button onclick="window.print()">Print This Page</button></div>\n'
   pageHtml+='<p style="text-align:center">File:'+paramsSession[3].textContent+' Date:'+date.getDate()+'-'+
             (date.getMonth()+1)+'-'+date.getFullYear()+'@'+date.getHours()+':'+date.getMinutes()+'</p>'

   var plotDiv_ids = Array.from(document.querySelectorAll(".js-plotly-plot")).map( (element)=>{return element.id} )
   for(const id of plotDiv_ids){
    await Plotly.toImage(id,{format:'svg'}).then((dataURL)=>{pageHtml+='<div id='+id+'><img style="width:100%" src="'+dataURL+'"></div>\n'})
    pageHtml+="\n"+document.querySelector('#'+id+' p').outerHTML+"\n"
   }
   printHtml.document.write(pageHtml)
   printHtml.document.close();
}

    
/**
 * Submit the Validation Screen data including the selected global delimiter value and observed to expected fields mappings selected via dropdowns
 * This key variable mapping information is passed as a dictionary to the back end via the POST HTTP request
 */
function submitValidatedFields(){
    var selectedObj = $('table .form-select option:selected')
    SelectedValidatedFields = {};

    const form = document.createElement('form');
    form.method = 'POST';
    form.action = '/';
    document.body.appendChild(form);

    var rows_dom = document.getElementsByTagName('tr');
    var expectFieldsList = [];
    for (var i=1; i<document.getElementsByTagName('tr').length; i++){
        expectFieldsList.push(rows_dom[i].getElementsByTagName('td')[1].textContent);
    }

    console.log(expectFieldsList);
    for(var i=0; i<expectFieldsList.length; i++){
        console.log(expectFieldsList[i])
        if(selectedObj[i].value !== '') {
            SelectedValidatedFields[ expectFieldsList[i]  ] = selectedObj[i].value; //expected_field:observed_field: {50_alleles:''}
        }else{
            SelectedValidatedFields[ expectFieldsList[i] ] = 'notselected';
        }

    }

    console.log(SelectedValidatedFields);

    const hiddenField = document.createElement('input');
    hiddenField.type = 'hidden';
    hiddenField.name = 'validatedfields_exp2obs_map';
    hiddenField.value = JSON.stringify(SelectedValidatedFields);
    form.appendChild(hiddenField);
    const hiddenField2 = document.createElement('input');
    hiddenField2.type = 'hidden';
    hiddenField2.name = 'delimiter_symbol';
    hiddenField2.value = document.getElementById('delimiter_selector').value;
    form.appendChild(hiddenField2);

    document.getElementById('overlay').style.display='none'; //remove splash screen
    $("#load_spinner_div").removeClass("d-none"); //activate spinner
    $("#info_message_file_upload_request").addClass('d-none');//remove(); //remove upload data message

    console.log(form);
    form.submit(); //regular submit

}
/**
 * Clear session information when switching from the dashboard to custom plot build view or viceversa
 * This prevents unexpected behaviour and allows user to start again from scratch in each view mode
 */
function clearSession(targeturl){
    console.log(targeturl)
    console.log("clearSession()")
    $.ajax({
        url: "/clearsession",
        type: "GET",
        success: function(){
            window.location = targeturl;
        },
        error: function() {
            window.location = targeturl;
        }
    }); 
}

/**
 * The key function allowing to POST data from all data filters (the left control panel) via AJAX calls to the backend and 
 * extract Group #1 or unfiltered initial input data containing all fields as a CSV file that can be analyzed externally.
 * First function checks if there are any rendered plots at this point, otherwise aborts
 * @param {string} source_call_id - the tag identifier that called this function useful to apply different processing logic
 * @param {bool} extract_filtered_excel_data - used to generate CSV file to download based on current filters
 * @returns - a bool value or undefined based on the case
 */
function postPlotData(source_call_id=null, extract_filtered_excel_data = false) {
    if($('.js-plotly-plot').length === 0){
        alert("No rendered plots. Aborting");
        document.getElementById('percent_scale_toggle').checked=false;
        document.getElementById('log_scale_toggle').checked=false;
        return false
    }
    console.log('postPlotData() fx');
    console.log(source_call_id);
    console.log(extract_filtered_excel_data);
    let SelectedFieldsMap = {}; SelectedFieldsMap['datafilters2apply']={};
    //if user initialized change
    if(source_call_id === 'percent_scale_toggle' && document.querySelector('#percent_scale_toggle').checked){
        //add flag that % scale was selected
        SelectedFieldsMap['percent_yscale']='yes'
        $('#log_scale_toggle')[0].checked=false; //deactivate log scale toggle
    }else if(source_call_id === 'log_scale_toggle' && document.querySelector('#log_scale_toggle').checked){
        SelectedFieldsMap['log_yscale']='yes'
        $('#percent_scale_toggle')[0].checked=false; //deactivate percentage toggle
    }else if(document.querySelector('#percent_scale_toggle').checked){ //if already selected
        SelectedFieldsMap['percent_yscale']='yes'
    }else if(document.querySelector('#log_scale_toggle').checked){
        SelectedFieldsMap['log_yscale']='yes'
    }

    var select_tags = $("#accordion_section_filters_subset1").find("select");

    for(var i=0; i<select_tags.length; i++){
        var selected_options = $("#"+select_tags[i].id).val();
        if(selected_options.length > 0){
            for(var j=0; j<selected_options.length; j++){
                SelectedFieldsMap['datafilters2apply'][select_tags[i].id+'_'+j]=selected_options[j];
            }
        }
    }

    let ids=['start_date_filterset1', 'start_date_filterset2','end_date_filterset1', 'end_date_filterset2']
    for (const id of ids){
        if(id.match(/start_date/i)) {
            let selected_start_date = document.getElementById(id).value
            if (selected_start_date !== '') {
                SelectedFieldsMap['datafilters2apply'][id] = selected_start_date
            }
        }else if(id.match(/end_date/i)){
            let selected_end_date = document.getElementById(id).value
            if(selected_end_date  !== ''){
                SelectedFieldsMap['datafilters2apply'][id] = selected_end_date
            }
        }
    }


    let groupby_values_array=$('#groupby_selector').selectpicker('option:selected').val();
    let filters_group2_values=Array.from($("#accordion_section_filters_subset2").find("select")).map(i=>{return(i.value)}).filter(function(i){return i.length > 0})

    console.log(groupby_values_array)
    console.log(filters_group2_values)

    if (groupby_values_array.length > 1){
        alert('Only a single groupby variable is supported. You selected '+groupby_values_array.length+' values');
        return false;
    } else if (groupby_values_array.length >0 && filters_group2_values.length>0){
        alert("Can not have both filters for 'group #2' and 'group by' activated.\n'Group by' can only be applied to 'group #1'")
        return false;
    } else if (groupby_values_array.length === 1 && filters_group2_values.length === 0){
        console.log('group by filter applied');
        SelectedFieldsMap['groupby_selector_value']= groupby_values_array[0];
    } else if (filters_group2_values.length > 0 && groupby_values_array.length === 0) {
        console.log('secondary filters applied');
        var select_tags2 = $("#accordion_section_filters_subset2 :first-child").find("select");

        for (let i = 0; i < select_tags2.length; i++) {
            var selected_options2 = $("#" + select_tags2[i].id).val();

            if (selected_options2.length > 0) {
                for (let j = 0; j < selected_options2.length; j++) {
                    SelectedFieldsMap['datafilters2apply'][select_tags2[i].id + '_' + j] = selected_options2[j];
                }
                $('#groupby_selector').selectpicker('val', null); //deactivate any groupby previously selected values when filters group 2 active
            }
        }
    }

    console.log(SelectedFieldsMap)
    SelectedFieldsMap['datafilters2apply']=JSON.stringify(SelectedFieldsMap['datafilters2apply'])
    // POST request to extract current EXCEL dataframe (only valid for global or Group #1 filters)
    if (extract_filtered_excel_data === true){
        SelectedFieldsMap['get_excel_subset']='yes';
        console.log("Export filtered data to csv for user download");

        $.ajax({
            url: "/",
            type: "POST",
            data: SelectedFieldsMap,
            success: function (response) {
                let blob = new Blob([response], { type: 'text/plain' });
                let a = document.createElement('a');
                a.href = window.URL.createObjectURL(blob);
                a.download = "export_data.csv";
                a.click();
            },
            error:  function (request, status, error) {
                console.log(error);
                console.log(request.responseText);
            }
        });

        return () => undefined;
    }



    $("#load_spinner_div").removeClass("d-none");
    $('#content [id^="plotDiv"]').hide();
    $(".plottabs").hide();


    //default POST AFTER dashboard was loaded with initial data
    $.ajax({
        url: "/",
        type: "POST",
        data: SelectedFieldsMap,
        dataType: "json",
        success: function (plotsData, status, request) {
            console.log(plotsData)
            console.log(request)
            $("#load_spinner_div").addClass("d-none");
            $('#content [id^="plotDiv"]').show();
            $(".plottabs").show();
            if('error' in plotsData){
                alert(plotsData['error']);
            }else{
                renderplots(plotsData); renderTraceControls(); 
                populate_settings_applied();
                updateSunburstVisibleLevels();
            }
            

        },
        error:  function (request, status, error) {
            alert("ERROR (id:"+status+"): "+request.responseText+"\nSuggetions:\n1)Select other filters;\n2)Reupload data if session expired;\n3)Check connection or server is down.");
            $(".plottabs").show();
            $("#load_spinner_div").addClass("d-none");
            $('#content [id^="plotDiv"]').show();
            console.log(error);
            console.log(request)

        }
    });
}

/**
 * Populates the "Settings Applied" section of the left control panel listing the key information: 
 * input filename, session id, dashboard version, group by variable selected, filters group #1 and #2
 * Iterates over the group #1 and #2 filters and checks the group by variable and then updates the 'settings_selected_grid' div grid 
*/
function populate_settings_applied() {
    let groupbyval = $('#groupby_selector').selectpicker('option:selected').val();
    if (groupbyval.length === 1){
        document.getElementById("settings_selected_groupby").innerHTML = groupbyval[0]
    }else{
        document.getElementById("settings_selected_groupby").innerHTML='-'
    }

    let group1_filters_values=Array()
    document.querySelectorAll("#accordion_section_filters_subset1 select").forEach(item =>{
        Array.from(item.options).forEach(element => {
            if(element.selected){
                group1_filters_values.push(element.value)
            }
        });
    })

    let group2_filters_values = Array()
    document.querySelectorAll("#accordion_section_filters_subset2 select").forEach(item =>{
        Array.from(item.options).forEach(element => {
            if(element.selected){
                group2_filters_values.push(element.value)
            }
        });
    })

    if (group1_filters_values.length > 0){
        document.getElementById("settings_selected_group1").innerHTML = group1_filters_values.join(', ')
    }else{
        document.getElementById("settings_selected_group1").innerHTML = '-'
    }

    if (group2_filters_values.length > 0){
        document.getElementById("settings_selected_group2").innerHTML = group2_filters_values.join(', ')
    }else{
        document.getElementById("settings_selected_group2").innerHTML = '-'
    }
}

/**
 * Resizes plots if window size changes after user manipulations (resize, minimize, maximize, etc.)
 * All existing plots are being redrawn to the new width of the content div (i.e. right pane)
 */
function resizePlots(){
    console.log('resizing plots due to window change')
    let plots = document.getElementsByClassName('plotly');
    let plot_max_width = document.getElementById('content').clientWidth-50;
    for(let i=0; i<plots.length; i++){
        Plotly.relayout(plots[i].parentElement.id,{width: plot_max_width})
    }
}

/**
 * The key plot rendering function that iterates over the 15 graph identifiers stored in the graphKeys list and renders them in each separate tab
 * This function also generates a TAB for each figure and calls generate_caption() to parse figure caption text
 * @param {Map} graphsMap - a dictionary Object of Plotly figure objects stored in JSON text format assigned to a unique respective key. 
 * The graphsMap object has figure and captions as the main keys and is structured as follows 
 * {'figures':{'figure_key':'JSON figure object',...},'captions':{'figure_key':'caption text'}}
 */
function renderplots(graphsMap){
    console.log("renderplots()")
    var graphKeys = ['sample_accum_plot','geoloc_chart', 'age_distribution_chart','gender_distribution_chart','sample_source_type_distribution_chart',
    'sample_source_site_distribution_chart','primary_type_chart','secondary_type_chart','genetic_profile_bar_chart','genetic_components_bar_chart',
        'phenotypic_profile_bar_chart','phenotypic_components_bar_chart','hierarchy_of_clusters_sunburst_chart',
    'clusterid_codes_distribution_chart','investigationid_codes_distribution_chart'];

    console.log(graphsMap);
    if (Object.keys(graphsMap).length !== 0) {
        var nodeTabButtons = document.querySelector(".plottabs .buttons");
        var nodeTabButtonsCount = document.querySelectorAll(".plottabs .buttons button").length;
        var nodeTab = document.querySelector(".plottabs");
        var plotCounter= 0;
        //generate tabs buttons for each plot
        for(var i=0, len=graphKeys.length; i<len; i++){
            if(Object.keys(graphsMap['figures']).length === 0){ //no figures were provided for rendering
                break;
            }
            var key=graphKeys[i]

            if(graphsMap['figures'][key] !== '{}'){
                if (nodeTabButtonsCount === 0) {
                    var buttonElm = document.createElement("button")
                    buttonElm.classList.add("tablink");
                    buttonElm.setAttribute("onclick", "tabsPlotsControl('tabcontent_" + key + "',this)");
                    buttonElm.textContent = "P" + (plotCounter + 1);
                    buttonElm.name = "P" + (plotCounter + 1);
                    buttonElm.setAttribute('data-bs-toggle','tooltip');
                    buttonElm.setAttribute('data-bs-animation','false');
                    buttonElm.setAttribute('data-bs-trigger','hover');
                    buttonElm.setAttribute('data-bs-placement','bottom');
                    buttonElm.setAttribute('title',key);

                    var tabContentElm = document.createElement("div");
                    tabContentElm.classList.add("tabcontent");
                    tabContentElm.id = "tabcontent_" + key;
                    var plotlyDiv = document.createElement("div");
                    plotlyDiv.id = "plotDiv_" + key;
                    tabContentElm.appendChild(plotlyDiv)

                    nodeTabButtons.appendChild(buttonElm);
                    nodeTab.append(tabContentElm);
                }

                Plotly.react('plotDiv_' + key, JSON.parse(graphsMap['figures'][key]));
                generate_caption(graphsMap['captions'][key], 'plotDiv_' + key);

                plotCounter++;
            }

        }

        if (plotCounter !==0) {
            var tabsDOM = Array.from(document.getElementsByClassName('tablink'));
            tabsDOM.forEach((tab) => {
                tab.style.width = String(100 / tabsDOM.length) + "%"
            });
            document.getElementsByClassName("plottabs")[0].classList.remove("d-none");

            document.querySelector(".plottabs .buttons .tablink").click(); //click on the first one
            resizePlots();
        }
    }

}

/**
 * Generates a caption by accessing a specified plot <div> with the plot. Creates a new caption in the <p> tag or replaces text if it already exists 
 * @param {String} caption - The text of a figure caption to add or replace
 * @param {String} div_id - The id of the main plot div storing the Plotly plot and a caption 
 */
function generate_caption(caption, div_id){
    var element = document.createElement('p');
    element.innerText = caption;
    element.style.textAlign = "center"; element.style.fontWeight = "bold";
    var div_plot=document.getElementById(div_id);
    //console.log(div_plot);
    if(div_plot.querySelector("p")){
        div_plot.querySelector("p").replaceWith(element);
    }else {
        div_plot.append(element);
    }
}

/**
 * Styles the clicked tab based on defined CSS styles and hides other plots. Makes clicked tab grey and title text bold
 * @param {String} tabName - the id of the div storing the tab content corresponding to the clicked tab button (i.e. tab label such as P1)
 * @param {Object DOM} elmnt -  The <button> DOM element of a plot tab to style
 */
function tabsPlotsControl(tabName,elmnt) {
    console.log('tabsPlotsControl()')
    var i, tabcontent, tablinks;
    tabcontent = document.getElementsByClassName("tabcontent");

    for (i = 0; i < tabcontent.length; i++) {
        tabcontent[i].style.display = "none";
    }
    //remove previous styling if it exists to not accumulate previous changes
    tablinks = document.getElementsByClassName("tablink");
    for (i = 0; i < tablinks.length; i++) {
        tablinks[i].style.fontWeight = "";
        tablinks[i].style.background = "";

    }
    document.getElementById(tabName).style.display = "block";
    elmnt.style.fontWeight="bold";
    elmnt.style.background='darkgray';

}

/**
 * Starts selected file upload via an AJAX call and updates a progress bar. Upon completion writes a new HTML page with variable validation screen
 * If error, this will be shown in the browser console
 */
function startFileUpload(){
        console.log('startFileUpload()')
        $('#content [id^="plotDiv"]').hide()
        $('.plottabs').hide()
        $("#load_spinner_div").removeClass("d-none"); //show load spinner upon submission of the upload
        var processUploadBar = $(".progressUploadBar")
        $.ajax({
            xhr: function() {
                var xhr = new XMLHttpRequest();
                xhr.upload.addEventListener("progress", progressHandler, false);
                console.log(xhr);
                return xhr;
            },
            type: "POST",
            data: new FormData($("#upload_file_form")[0]),
            contentType: false,
            cache: false,
            processData:false,
            beforeSend: function(){
                processUploadBar[1].value = 0;
                processUploadBar[0].style.display='inline';
                processUploadBar[1].style.display='inline';

            },
            success : function(data){
                //console.log(data);
                document.open();
                document.write(data);
                document.close();
            },
            error: function (request, status, error) {
                alert("error while uploading file and rendering validation screen");
                console.log(error);
                document.getElementById('load_spinner_div').classList.add('d-none');
                document.getElementById('info_message_file_upload_request').classList.remove('d-none');

            }


        });


}

/**
 * Activate/Unlock all inactive 'Observed field' dropdowns in validation screen after user clicks on the lock icon
 * This allows user to specify a different field value for matched fields (that are automatically greyed out 
 * to prevent dublication of the expectd field names)
 */
function unlock_observed_fields(){
    document.querySelectorAll('.input_variables_table select').forEach( (i)=>{i.removeAttribute('disabled')})
}
