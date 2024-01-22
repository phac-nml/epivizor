from tests import client
from app import app
import os, pathlib



def test_landing_load(client):
    response = client.get("/")
    assert "<title>EpiVizor</title>" in response.data.decode()


def test_upload(client):
    file = "ecoli_sample_data.csv"
    path2file = os.path.join(pathlib.Path(__file__).parents[1].resolve(),'example',file)
    response = client.post("/", data={
        "file": (open(path2file, 'rb'), file),
        "content_type":'multipart/form-data'
    })
    assert response.status_code == 200
    assert 'ecoli_sample_data.csv' in response.data.decode()

    response = client.post("/", data={
        "validatedfields_exp2obs_map": '{"age":"age","cluster_id":"cluster_id","date":"date","gender":"gender","genetic_profile":"genetic_profile","geoloc_id":"geoloc_id","hierarchical_subtype":"hierarchical_subtype","investigation_id":"investigation_id","phenotypic_profile":"phenotypic_profile","primary_type":"primary_type","sample_id":"sample_id","secondary_type":"secondary_type","source_site":"source_site","source_type":"source_type"}',
        'delimiter_symbol': '|'
    }
    )
   
    assert response.status_code == 200
    assert "captions" in response.data.decode()
    assert "figures" in response.data.decode() 
    