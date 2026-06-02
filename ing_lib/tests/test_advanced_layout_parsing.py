
import pytest
import os
import tempfile
import json
from unittest.mock import patch, MagicMock
from apps.ProjConfigCreateUpdateCS import parse_custom_script_json

@pytest.fixture
def temp_json_with_advanced_layout():
    """Create a temporary JSON file with advanced layout for testing."""
    script_content = "#!/bin/bash\necho 'advanced layout test'"
    json_content = {
        "script_name": "advanced_layout_script",
        "script_path": "advanced.sh",
        "description": "Test advanced layout parsing from JSON",
        "outputs": [
            {"name": "my_image", "type": "IMAGE"},
            {"name": "my_series", "type": "SERIES"}
        ],
        "layout": [
            {
                "entry": "FALSE",
                "content": {
                    "contentlayout": [
                        {
                            "layout_type": "IMAGE",
                            "field_name": "my_image"
                        }
                    ]
                },
                "results": {
                    "resultslayout": [
                        {
                            "layout_type": "SERIES",
                            "field_name": "my_series",
                            "series_config": []
                        }
                    ]
                }
            }
        ]
    }
    
    with tempfile.TemporaryDirectory() as temp_dir:
        json_file = os.path.join(temp_dir, 'advanced_layout.json')
        script_file = os.path.join(temp_dir, 'advanced.sh')
        
        with open(json_file, 'w') as f:
            json.dump(json_content, f)
            
        with open(script_file, 'w') as f:
            f.write(script_content)
            
        yield json_file

def test_parse_json_with_advanced_layout(temp_json_with_advanced_layout):
    """Test that advanced layout with image and series is parsed correctly from JSON."""
    script_data, script_id = parse_custom_script_json(temp_json_with_advanced_layout, '/opt/scripts')
    
    assert 'layout' in script_data
    assert len(script_data['layout']) == 1
    
    section = script_data['layout'][0]
    
    # Check content layout for image
    assert 'content' in section
    content_layout = section['content']['contentlayout']
    assert len(content_layout) == 1
    image_item = content_layout[0]
    assert image_item['layout_type'] == 'IMAGE'
    assert image_item['field_name'] == 'my_image'
    
    # Check results layout for series
    assert 'results' in section
    results_layout = section['results']['resultslayout']
    assert len(results_layout) == 1
    series_item = results_layout[0]
    assert series_item['layout_type'] == 'SERIES'
    assert series_item['field_name'] == 'my_series' 