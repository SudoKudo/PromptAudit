var easy2map_imgmap_functions = (function() {

    //change 'border_width' into 'Border Width', for example
    normaliseCSSElement = function(item) {
        item = replaceAll(item, "_", " ");
        item = item.toLowerCase().replace(/\b[a-z]/g, function(letter) {
            return letter.toUpperCase();
        });
        return item;
    },
            //refresh the example map
            refreshExampleMap = function(saveMapToDatabase) {

        var templateID = parseInt(jQuery("#MapTemplateName").val());
        var proVersion = !!jQuery("#photoSize").attr("proVersion");

        for (var t = 0; t < $arrTemplates.length; t++) {

            var template = $arrTemplates[t];

            if (parseInt(template.ID) == templateID) {

                jQuery('#divPreview').html(replaceAll(template.TemplateHTML, '[siteurl]', $pluginsURL));
                if (proVersion === true)
                    jQuery('#easy2mapphotologo').remove();

                jQuery('[id ^= styleElement]').each(function() {
                    jQuery('#divMapParent').css(replaceAll(jQuery(this).attr('item'), "_", "-"), jQuery(this).attr('value'));
                });

                jQuery('[id ^= stylePhotoElement]').each(function() {

                    if (jQuery(this).attr('item') === "width") {
                        jQuery('#divMapParent').css("width", jQuery(this).attr('value'));
                        jQuery('#easy2mapmainimage').css("width", '');

                    } else {
                        jQuery('#easy2mapmainimage').css(replaceAll(jQuery(this).attr('item'), "_", "-"), jQuery(this).attr('value'));
                    }
                });

                jQuery('[id ^= styleMapElement]').each(function() {
                    jQuery('#divMap').css(replaceAll(jQuery(this).attr('item'), "_", "-"), jQuery(this).attr('value'));
                });

                jQuery("#easy2mapIimgShadow").width(jQuery("#divMapParent").width());
                jQuery("#easy2mapIimgShadow").width(jQuery("#divMapParent").width());
                jQuery("#easy2mapIimgShadow").css('marginLeft', jQuery("#divMapParent").css('marginLeft'));
                jQuery("#easy2mapIimgShadow").css('marginRight', jQuery("#divMapParent").css('marginRight'));

            }
        }

        //save the map to the database if required to do so
        if (!!saveMapToDatabase) {
            easy2map_imgmap_functions.saveMap(false, false);
        }

        easy2map_imgmap_functions.displayGoogleMap();

        google.maps.event.addDomListener(window, 'load', easy2map_imgmappin_functions.retrieveMapPoints());

    };

    //retrieve map's CSS elements for saving to the database
    retrieveMapCSS = function() {

        var arrCSS = [];

        jQuery('[id ^= styleMapElement]').each(function() {
            var item = replaceAll(jQuery(this).attr('item'), "_", "-");
            arrCSS[item] = jQuery(this).attr('value');
        });

        var options = {
            formatOutput: true,
            rootTagName: 'settings'
        };
        return jQuery.json2xml(arrCSS, options);

    };

    //retrieve map's CSS elements for saving to the database
    retrieveParentCSS = function() {

        var arrCSS = [];

        jQuery('[id ^= styleElement]').each(function() {
            var item = replaceAll(jQuery(this).attr('item'), "_", "-");
            arrCSS[item] = jQuery(this).attr('value');
        });

        var options = {
            formatOutput: true,
            rootTagName: 'settings'
        };
        return jQuery.json2xml(arrCSS, options);

    };

    //retrieve map's CSS elements for saving to the database
    retrievePhotoCSS = function() {

        var arrCSS = [];

        jQuery('[id ^= stylePhotoElement]').each(function() {
            var item = replaceAll(jQuery(this).attr('item'), "_", "-");
            arrCSS[item] = jQuery(this).attr('value');
        });

        var options = {
            formatOutput: true,
            rootTagName: 'settings'
        };
        return jQuery.json2xml(arrCSS, options);

    };

    //retrieve the map settings for rendering/saving the map
    retrieveMapOptions = function($lat, $lng, $zoom) {

        var $mapType = jQuery('#mapType').val().toUpperCase();
        if ($mapType === "ROADMAP")
            $mapType = google.maps.MapTypeId.ROADMAP;
        else if ($mapType === "HYBRID")
            $mapType = google.maps.MapTypeId.HYBRID;
        else if ($mapType === "SATELLITE")
            $mapType = google.maps.MapTypeId.SATELLITE;
        else if ($mapType === "TERRAIN")
            $mapType = google.maps.MapTypeId.TERRAIN;
        else
            $mapType = google.maps.MapTypeId.ROADMAP;

        var $mapTypeControl_style = google.maps.MapTypeControlStyle.DEFAULT;
        var $mapTypeControl_position = google.maps.ControlPosition.TOP_LEFT;
        var $latlng = new google.maps.LatLng($lat, $lng);

        var mapOptions = {
            zoom: $zoom,
            center: $latlng,
            mapTypeId: $mapType,
            mapTypeControl: false,
            clusterpins: false,
            trafficlayer: false,
            transitlayer: false,
            bicyclelayer: false,
            polyline_strokecolor: '000000',
            polyline_opacity: '1.0',
            polyline_strokeweight: '1',
            mapTypeControlOptions: {
                style: $mapTypeControl_style,
                position: $mapTypeControl_position
            },
            zoomControl: true,
            navigationControl: true,
            zoomControlOptions: {
                style: google.maps.ZoomControlStyle.SMALL,
                position: google.maps.ControlPosition.LEFT_TOP
            },
            scaleControl: false,
            scaleControlOptions: {
                position: google.maps.ControlPosition.TOP_LEFT
            },
            streetViewControl: true,
            panControl: false,
            draggable: true
        };

        return mapOptions;

    };

    //retrieve all map templates from the database
    retrieveMapTemplates = function(mapID, templateID) {

        jQuery.ajax({
            type: 'POST',
            url: ajaxurl,
            dataType: 'json',
            data: {
                mapID: mapID,
                action: "e2m_img_retrieve_map_templates"
            },
            success: function(arrTemplates) {

                $arrTemplates = arrTemplates;

                for (var t = 0; t < arrTemplates.length; t++) {
                    jQuery("#MapTemplateName").append("<option value='" + arrTemplates[t].ID + "'>" + arrTemplates[t].TemplateName + "</option>");
                }

                jQuery("#MapTemplateName").val(templateID);

                if (jQuery("#MapTemplateName").val() == null) {
                    jQuery("#MapTemplateName").val(arrTemplates[0].ID);
                }

                easy2map_imgmap_functions.changeMapTemplate();
            },
            error: function(XMLHttpRequest, textStatus, errorThrown) {
                alert(errorThrown);
            }
        });

    };

    hexToRgb = function(hex) {
        var result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
        return result ? {
            r: parseInt(result[1], 16),
            g: parseInt(result[2], 16),
            b: parseInt(result[3], 16)
        } : null;
    };


    return {
        copyMapSettings: function() {

            if (!!jQuery('#CopyMapSettings').val() === false)
                return;
            jQuery('#CopyMapID').val(jQuery('#CopyMapSettings').val());
            document.getElementById("formCopymapSettings").submit();
        },
        //Change a single CSS value
        changeElementValue: function(i, element, proVersion) {

            if (proVersion == false)
                return;

            var attribute, value;

            if (element === 1) {
                attribute = jQuery('#styleElement' + i).attr('item');
                if (attribute == "box_shadow")
                    value = jQuery('#styleElement' + i).attr('value');
                else
                    value = replaceAll(jQuery('#styleElement' + i).attr('value'), "px", "");
            } else if (element === 2) {
                attribute = jQuery('#stylePhotoElement' + i).attr('item');
                if (attribute == "box_shadow")
                    value = jQuery('#stylePhotoElement' + i).attr('value');
                else
                    value = replaceAll(jQuery('#stylePhotoElement' + i).attr('value'), "px", "");
            } else {
                attribute = jQuery('#styleMapElement' + i).attr('item');
                if (attribute == "box_shadow")
                    value = jQuery('#styleMapElement' + i).attr('value');
                else
                    value = replaceAll(jQuery('#styleMapElement' + i).attr('value'), "px", "");
            }

            $styleElementIndex = i;
            $styleSelectedElement = element;
            jQuery('div[id ^= div_edit_]').hide();

            switch (attribute) {

                case "border_style":
                    {
                        jQuery('#tdheading_style').html("Border Style");
                        jQuery('#div_edit_style').modal();
                        jQuery('#txtDefaultValue_style').val(value).focus();
                        break;
                    }

                case "box_shadow":
                    {
                        jQuery('#tdheading_style').html("Shadow Style");
                        jQuery('#div_edit_shadow').modal();
                        jQuery('#txtDefaultValue_shadow').val(value).focus();
                        break;
                    }

                case "border_width":
                    {

                        jQuery('#tdheading_pixel').html("Border Width");
                        jQuery('#txtDefaultValue_pixel').find('option').remove();
                        for (var i = parseInt(0); i <= parseInt(50); i++)
                            jQuery('#txtDefaultValue_pixel').append('<option value="' + i + '">' + i + '</option>');
                        jQuery('#div_edit_pixel').modal();
                        jQuery('#txtDefaultValue_pixel').val(value).focus();
                        break;
                    }

                case "width":
                    {

                        if (value.indexOf("%") != -1) {

                            //percentage-based width
                            jQuery('#tdheading_percentage').html("Width");
                            jQuery('#txtDefaultValue_percentage').find('option').remove();
                            for (var i = parseInt(1); i <= parseInt(110); i++)
                                jQuery('#txtDefaultValue_percentage').append('<option value="' + i + '">' + i + '</option>');
                            jQuery('#div_edit_percentage').modal();
                            jQuery('#txtDefaultValue_percentage').val(replaceAll(value, "%", "")).focus();

                        } else {

                            //pixel-based width
                            jQuery('#tdheading_pixel').html("Width");
                            jQuery('#div_edit_pixel').modal();
                            jQuery('#txtDefaultValue_pixel').val(value).focus();
                        }


                        break;
                    }

                case "height":
                    {

                        jQuery('#tdheading_pixel').html("Height");
                        jQuery('#txtDefaultValue_pixel').find('option').remove();
                        for (var i = parseInt(10); i <= parseInt(2000); i++)
                            jQuery('#txtDefaultValue_pixel').append('<option value="' + i + '">' + i + '</option>');
                        jQuery('#div_edit_pixel').modal();
                        jQuery('#txtDefaultValue_pixel').val(value).focus();
                        break;
                    }

                case "margin_bottom":
                    {

                        jQuery('#tdheading_margin').html("Bottom Margin");
                        jQuery('#txtDefaultValue_margin').find('option').remove();
                        jQuery('#txtDefaultValue_margin').append('<option value="auto">auto</option>');
                        for (var i = parseInt(-50); i <= parseInt(500); i++)
                            jQuery('#txtDefaultValue_margin').append('<option value="' + i + '">' + i + '</option>');
                        jQuery('#div_edit_margin').modal();
                        jQuery('#txtDefaultValue_margin').val(value).focus();
                        break;
                    }

                case "margin_top":
                    {

                        jQuery('#tdheading_margin').html("Top Margin");
                        jQuery('#txtDefaultValue_margin').find('option').remove();
                        jQuery('#txtDefaultValue_margin').append('<option value="auto">auto</option>');
                        for (var i = parseInt(-50); i <= parseInt(500); i++)
                            jQuery('#txtDefaultValue_margin').append('<option value="' + i + '">' + i + '</option>');
                        jQuery('#div_edit_margin').modal();
                        jQuery('#txtDefaultValue_margin').val(value).focus();
                        break;
                    }

                case "margin_left":
                    {

                        jQuery('#tdheading_margin').html("Left Margin");
                        jQuery('#txtDefaultValue_margin').find('option').remove();
                        jQuery('#txtDefaultValue_margin').append('<option value="auto">auto</option>');
                        for (var i = parseInt(-50); i <= parseInt(500); i++)
                            jQuery('#txtDefaultValue_margin').append('<option value="' + i + '">' + i + '</option>');
                        jQuery('#div_edit_margin').modal();
                        jQuery('#txtDefaultValue_margin').val(value).focus();
                        break;
                    }

                case "margin_right":
                    {

                        jQuery('#tdheading_margin').html("Right Margin");
                        jQuery('#txtDefaultValue_margin').find('option').remove();
                        jQuery('#txtDefaultValue_margin').append('<option value="auto">auto</option>');
                        for (var i = parseInt(-50); i <= parseInt(500); i++)
                            jQuery('#txtDefaultValue_margin').append('<option value="' + i + '">' + i + '</option>');
                        jQuery('#div_edit_margin').modal();
                        jQuery('#txtDefaultValue_margin').val(value).focus();
                        break;
                    }

                case "border_radius":
                    {

                        jQuery('#tdheading_pixel').html("Border Radius");
                        jQuery('#txtDefaultValue_pixel').find('option').remove();
                        for (var i = parseInt(0); i <= parseInt(500); i++)
                            jQuery('#txtDefaultValue_pixel').append('<option value="' + i + '">' + i + '</option>');
                        jQuery('#div_edit_pixel').modal();
                        jQuery('#txtDefaultValue_pixel').val(value).focus();
                        break;
                    }

                case "border_color":
                    {

                        jQuery('#tdheading_color').html("Border Color");
                        jQuery('#div_edit_color').modal();
                        jQuery('#txtDefaultValue_color').val(value).focus();
                        jQuery('#txtDefaultValue_color').css('background-color', value);
                        jQuery('#colourpicker').attr('data-color', hexToRgb(value));
                        jQuery('#liDefaultValue_color').css('background-color', value);
                        break;
                    }

                case "background_color":
                    {

                        jQuery('#tdheading_color').html("Background Color");
                        jQuery('#div_edit_color').modal();
                        jQuery('#txtDefaultValue_color').val(value).focus();
                        jQuery('#txtDefaultValue_color').css('background-color', value);
                        jQuery('#colourpicker').attr('data-color', hexToRgb(value));
                        jQuery('#liDefaultValue_color').css('background-color', value);
                        break;
                    }

            }

        },
        //change a map's template
        changeMapTemplate: function() {

            var templateID = jQuery("#MapTemplateName").val();
            jQuery('#divPreview').html('');
            var proVersion = !!jQuery("#photoSize").attr("proVersion");

            for (var t = 0; t < $arrTemplates.length; t++) {

                var template = $arrTemplates[t];
                if (parseInt(template.ID) == templateID) {

                    jQuery('#MapTemplateExampleImg').attr("src", $pluginsURL + template.ExampleImage);

                    //parent container style
                    var css = jQuery.xml2json(template.CSSValues);
                    jQuery('#MapTemplateCSS').html('');

                    var j = 0;
                    for (var item in css) {

                        jQuery('#MapTemplateCSS').append('<div ' + (item === "width" || item === "height" ? "style='display:none;'" : "") + ' class="cssStyleEditorParent"><a id="styleElement' + j + '" class="cssEdit" href="javascript:easy2map_imgmap_functions.changeElementValue(' + j + ', 1, ' + proVersion + ');" item="' + item + '" value="' + css[item] + '">' + normaliseCSSElement(item) + " (" + css[item] + ")</a></div>");
                        j += 1;
                    }

                    //photo container size
                    css = jQuery.xml2json(template.CSSValuesPhoto);
                    jQuery('#MapTemplatePhotoCSS').html('');

                    j = 0;
                    var photoWidth = "", photoHeight = "";
                    for (var item in css) {

                        if (item === "width") {
                            photoWidth = css[item];
                        }
                        if (item === "height") {
                            photoHeight = css[item];
                        }

                        jQuery('#MapTemplatePhotoCSS').append('<div ' + (item === "width" || item === "height" ? "style='display:none;'" : "") + ' class="cssStyleEditorParent"><a id="stylePhotoElement' + j + '" class="cssEdit" href="javascript:easy2map_imgmap_functions.changeElementValue(' + j + ', 2, ' + proVersion + ');" item="' + item + '" value="' + css[item] + '">' + normaliseCSSElement(item) + " (" + css[item] + ")</a></div>");
                        j += 1;
                    }

                    jQuery("#photoSize").html("");
                    //jQuery("#photoSize").append("<option value='640px,480px'>640px x 480px</option>");
                    jQuery("#photoSize").append("<option value='520px,390px'>520px x 390px</option>");
                    //jQuery("#photoSize").append("<option value='425px,319px'>425px x 319px</option>");
                    jQuery("#photoSize").append("<option value='custom'>Set Custom Size</option>");
                    jQuery("#photoSize").val(photoWidth + "," + photoHeight).attr("selected", "selected");

                    if (jQuery("#photoSize option:selected").val() != photoWidth + "," + photoHeight) {
                        jQuery("#photoSize option:eq(" + parseInt(jQuery("#photoSize option").length - 2) + ")").after("<option selected='selected' value='" + photoWidth + "," + photoHeight + "'>" + photoWidth + " x " + photoHeight + "</option>");
                    }

                    //map container size
                    css = jQuery.xml2json(template.CSSValuesMap);
                    jQuery('#MapTemplateMapCSS').html('');

                    j = 0;
                    var mapWidth = "", mapHeight = "";
                    for (var item in css) {

                        if (item === "width") {
                            mapWidth = css[item];
                        }
                        if (item === "height") {
                            mapHeight = css[item];
                        }

                        jQuery('#MapTemplateMapCSS').append('<div ' + (item === "width" || item === "height" ? "style='display:none;'" : "") + ' class="cssStyleEditorParent"><a id="styleMapElement' + j + '" class="cssEdit" href="javascript:easy2map_imgmap_functions.changeElementValue(' + j + ', 3, ' + proVersion + ');" item="' + item + '" value="' + css[item] + '">' + normaliseCSSElement(item) + " (" + css[item] + ")</a></div>");
                        j += 1;
                    }

                    jQuery("#mapSize").html("");
                    jQuery("#mapSize").append("<option value='custom'>Set Custom Size</option>");
                    jQuery("#mapSize").val(mapWidth + "," + mapHeight).attr("selected", "selected");

                    var displaySize = mapWidth.length > 0 ? mapWidth + " x " + mapHeight : "Height: " + mapHeight;

                    if (jQuery("#mapSize option:selected").val() != mapWidth + "," + mapHeight) {
                        jQuery("#mapSize option:eq(" + parseInt(jQuery("#mapSize option").length - 2) + ")").after("<option selected='selected' value='" + mapWidth + "," + mapHeight + "'>" + displaySize + "</option>");
                    }
                }
            }

            refreshExampleMap(true);
        },
        disableHover: function() {
            jQuery("#easy2mapmainimage").unbind('mouseenter mouseleave');
        },
        displayGoogleMap: function() {

            var settings = jQuery.xml2json($mapSettings.Settings);
            var $lat = settings.lattitude;
            var $lng = settings.longitude;
            var $zoom = parseInt(settings.zoom);

            if ($map != null) {
                $lat = $map.getCenter().lat();
                $lng = $map.getCenter().lng();
                $zoom = $map.getZoom();
            }

            var mapOptions = retrieveMapOptions($lat, $lng, $zoom);

            $map = new google.maps.Map(document.getElementById("divMap"), mapOptions);
            $overlay = new google.maps.OverlayView();
            $overlay.draw = function() {
            };
            $overlay.setMap($map);

            if (mapOptions.trafficlayer) {
                var trafficLayer = new google.maps.TrafficLayer();
                trafficLayer.setMap($map);
            }

            if (mapOptions.transitlayer) {
                var transitLayer = new google.maps.TransitLayer();
                transitLayer.setMap($map);
            }

            if (mapOptions.bicyclelayer) {
                var bicycleLayer = new google.maps.BicyclingLayer();
                bicycleLayer.setMap($map);
            }

        },
        enableHover: function() {

            jQuery("#easy2mapslider").show();

            jQuery("#divMap").hover(function() {
                jQuery("#easy2mapslider").hide();

            });

            jQuery("#easy2mapmainimage").hover(function() {

                if (jQuery('#divMap:hover').length === 0) {
                    jQuery("#easy2mapslider").fadeIn();
                } else {
                    jQuery("#easy2mapslider").hide();
                }

            }
            , function() {
                jQuery(this).find("#easy2mapslider").fadeOut();
            }
            );

        },
        //allow the user to set a custom size for their map
        setCustomMapSize: function() {

            if (isNaN(document.getElementById('txtCustomMapWidthValue').value))
                return;
            if (isNaN(document.getElementById('txtCustomMapHeightValue').value))
                return;

            if (parseInt(document.getElementById('txtCustomMapWidthValue').value) < 0)
                return;
            if (parseInt(document.getElementById('txtCustomMapHeightValue').value) < 0)
                return;

            var width = jQuery('#txtCustomMapWidthValue').val().length === 0 ? '' : jQuery('#txtCustomMapWidthValue').val() + jQuery('#mapWidthDimension').val();
            var height = jQuery('#txtCustomMapHeightValue').val() + 'px';
            easy2map_imgmap_functions.changeMapSize(width + ',' + height);
        },
        //allow the user to set a custom size for their map
        setCustomPhotoSize: function() {

            if (isNaN(document.getElementById('txtCustomPhotoWidthValue').value))
                return;
            if (isNaN(document.getElementById('txtCustomPhotoHeightValue').value))
                return;

            if (parseInt(document.getElementById('txtCustomPhotoWidthValue').value) < 0)
                return;
            if (parseInt(document.getElementById('txtCustomPhotoHeightValue').value) < 0)
                return;

            var width = jQuery('#txtCustomPhotoWidthValue').val() + jQuery('#photoWidthDimension').val();
            var height = jQuery('#txtCustomPhotoHeightValue').val() + 'px';
            easy2map_imgmap_functions.changePhotoSize(width + ',' + height);
        },
        //save the map's new size 
        changeMapSize: function(size) {

            if (size == "custom") {
                jQuery('#txtCustomMapWidthValue').val('').hide();
                jQuery('[id ^= styleMapElement]').each(function() {

                    if (jQuery(this).attr('item') === 'width') {

                        var currentWidth = jQuery(this).attr('value');

                        jQuery('#txtCustomMapWidthValue').val(parseInt(currentWidth));
                        if (currentWidth.indexOf('px') > 0) {
                            jQuery('#mapWidthDimension').val('px');
                        } else {
                            jQuery('#mapWidthDimension').val('%');
                        }
                        jQuery('#txtCustomMapWidthValue').val(parseInt(currentWidth)).show();

                    }
                    if (jQuery(this).attr('item') === 'height') {
                        jQuery('#txtCustomMapHeightValue').val(parseInt(jQuery(this).attr('value')));
                    }
                });
                jQuery('#div_edit_mapwidthheight').modal();
                return;
            }
            var arrSize = size.split(',');
            if (arrSize.length < 2)
                return;

            jQuery('[id ^= styleMapElement]').each(function() {

                if (jQuery(this).attr('item') === 'width') {
                    jQuery(this).attr('value', arrSize[0]);
                    jQuery(this).html('Width' + ' (' + arrSize[0] + ')');
                }
                if (jQuery(this).attr('item') === 'height') {
                    jQuery(this).attr('value', arrSize[1]);
                    jQuery(this).html('Height' + ' (' + arrSize[1] + ')');
                }

            });

            jQuery("#mapSize").val(arrSize[0] + "," + arrSize[1]).attr("selected", "selected");

            if (jQuery("#mapSize option:selected").val() != arrSize[0] + "," + arrSize[1]) {
                jQuery("#mapSize option:eq(" + parseInt(jQuery("#mapSize option").length - 2) + ")").after("<option selected='selected' value='" + arrSize[0] + "," + arrSize[1] + "'>" + arrSize[0] + " x " + arrSize[1] + "</option>");
            }

            refreshExampleMap(true);

        },
        //save the map's new size 
        changePhotoSize: function(size) {

            if (size == "custom") {
                jQuery('[id ^= stylePhotoElement]').each(function() {

                    if (jQuery(this).attr('item') === 'width') {

                        var currentWidth = jQuery(this).attr('value');
                        if (currentWidth.indexOf('px') > 0) {
                            jQuery('#photoWidthDimension').val('px');
                        } else {
                            jQuery('#photoWidthDimension').val('%');
                        }

                        jQuery('#txtCustomPhotoWidthValue').val(parseInt(currentWidth));

                    }
                    if (jQuery(this).attr('item') === 'height') {
                        jQuery('#txtCustomPhotoHeightValue').val(parseInt(jQuery(this).attr('value')));
                    }
                });
                jQuery('#div_edit_photowidthheight').modal();
                return;
            }
            var arrSize = size.split(',');
            if (arrSize.length < 2)
                return;

            jQuery('[id ^= stylePhotoElement]').each(function() {

                if (jQuery(this).attr('item') === 'width') {
                    jQuery(this).attr('value', arrSize[0]);
                    jQuery(this).html('Width' + ' (' + arrSize[0] + ')');
                }
                if (jQuery(this).attr('item') === 'height') {
                    jQuery(this).attr('value', arrSize[1]);
                    jQuery(this).html('Height' + ' (' + arrSize[1] + ')');
                }

            });

            jQuery("#photoSize").val(arrSize[0] + "," + arrSize[1]).attr("selected", "selected");

            if (jQuery("#photoSize option:selected").val() != arrSize[0] + "," + arrSize[1]) {
                jQuery("#photoSize option:eq(" + parseInt(jQuery("#photoSize option").length - 2) + ")").after("<option selected='selected' value='" + arrSize[0] + "," + arrSize[1] + "'>" + arrSize[0] + " x " + arrSize[1] + "</option>");
            }

            refreshExampleMap(true);

        },
        //retrieve map's settings from the database
        retrieveMapSettings: function(mapID) {

            jQuery.ajax({
                type: 'POST',
                url: ajaxurl,
                dataType: 'json',
                data: {
                    mapID: mapID,
                    action: "e2m_img_retrieve_map_settings"
                },
                success: function(mapSettings) {

                    $mapSettings = mapSettings;
                    jQuery('#draggable').attr("src", $mapSettings.DefaultPinImage);

                    var settings = jQuery.xml2json($mapSettings.Settings);
                    jQuery('#mapType').val(settings.mapType);
                    jQuery('#markerZoom').val(settings.markerzoom);

                    if ($mapSettings.MapName) {
                        jQuery('#mapName').val($mapSettings.MapName);
                        jQuery('#mapName2').html($mapSettings.MapName);
                    } else {
                        jQuery('#mapName2').html("Untitled Photo Map");
                    }

                    jQuery('#mapEditPencil').show();
                    retrieveMapTemplates(mapID, $mapSettings.TemplateID);

                },
                error: function(XMLHttpRequest, textStatus, errorThrown) {
                    alert(errorThrown);
                }
            });

        },
        //save the CSS element that has been edited
        saveItemValue: function() {

            var attribute;

            if ($styleSelectedElement === 1)
                attribute = jQuery('#styleElement' + $styleElementIndex).attr('item');
            else if ($styleSelectedElement === 2)
                attribute = jQuery('#stylePhotoElement' + $styleElementIndex).attr('item');
            else
                attribute = jQuery('#styleMapElement' + $styleElementIndex).attr('item');

            var alteredValue = '';
            switch (attribute) {
                case "border_style":
                    {
                        alteredValue = jQuery('#txtDefaultValue_style').val()
                        jQuery('#div_edit_style').hide();
                        break;
                    }
                case "box_shadow":
                    {
                        alteredValue = jQuery('#txtDefaultValue_shadow').val()
                        jQuery('#div_edit_shadow').hide();
                        break;
                    }
                case "border_width":
                    {
                        alteredValue = jQuery('#txtDefaultValue_pixel').val() + "px";
                        jQuery('#div_edit_pixel').hide();
                        break;
                    }
                case "width":
                    {

                        if (jQuery('#styleElement' + $styleElementIndex).attr('value').indexOf("%") != -1) {
                            //percentage-based width
                            alteredValue = jQuery('#txtDefaultValue_percentage').val() + "%";
                            jQuery('#div_edit_percentage').hide();
                        }
                        else {
                            //pixel based width
                            alteredValue = jQuery('#txtDefaultValue_pixel').val() + "px";
                            jQuery('#div_edit_pixel').hide();

                        }
                        break;
                    }
                case "height":
                    {
                        alteredValue = jQuery('#txtDefaultValue_pixel').val() + "px";
                        jQuery('#div_edit_pixel').hide();
                        break;
                    }
                case "margin_top":
                    {
                        alteredValue = jQuery('#txtDefaultValue_margin').val();
                        if (alteredValue != "auto")
                            alteredValue += "px";
                        jQuery('#div_edit_margin').hide();
                        break;
                    }
                case "margin_bottom":
                    {
                        alteredValue = jQuery('#txtDefaultValue_margin').val();
                        if (alteredValue != "auto")
                            alteredValue += "px";
                        jQuery('#div_edit_margin').hide();
                        break;
                    }
                case "margin_left":
                    {
                        alteredValue = jQuery('#txtDefaultValue_margin').val();
                        if (alteredValue != "auto")
                            alteredValue += "px";
                        jQuery('#div_edit_margin').hide();
                        break;
                    }
                case "margin_right":
                    {
                        alteredValue = jQuery('#txtDefaultValue_margin').val();
                        if (alteredValue != "auto")
                            alteredValue += "px";
                        jQuery('#div_edit_margin').hide();
                        break;
                    }

                case "border_color":
                    {
                        alteredValue = jQuery('#txtDefaultValue_color').val();
                        jQuery('#tdItemElementValue').css('background-Color', jQuery('#txtDefaultValue_color').val());
                        jQuery('#div_edit_color').hide();
                        break;
                    }
                case "background_color":
                    {
                        alteredValue = jQuery('#txtDefaultValue_color').val();
                        jQuery('#tdItemElementValue').css('background-Color', jQuery('#txtDefaultValue_color').val());
                        jQuery('#div_edit_color').hide();
                        break;
                    }
                case "z-index":
                    {
                        alteredValue = jQuery('#txtDefaultValue_pixel').val();
                        jQuery('#div_edit_pixel').hide();
                        break;
                    }
                case "border_radius":
                    {
                        alteredValue = jQuery('#txtDefaultValue_pixel').val() + "px";
                        jQuery('#div_edit_pixel').hide();
                        break;
                    }
            }

            if ($styleSelectedElement === 1) {
                jQuery('#styleElement' + $styleElementIndex).attr('value', alteredValue);
                jQuery('#styleElement' + $styleElementIndex).html(normaliseCSSElement(attribute) + ' (' + alteredValue + ')');

            }
            else if ($styleSelectedElement === 2) {
                jQuery('#stylePhotoElement' + $styleElementIndex).attr('value', alteredValue);
                jQuery('#stylePhotoElement' + $styleElementIndex).html(normaliseCSSElement(attribute) + ' (' + alteredValue + ')');

            }
            else {
                jQuery('#styleMapElement' + $styleElementIndex).attr('value', alteredValue);
                jQuery('#styleMapElement' + $styleElementIndex).html(normaliseCSSElement(attribute) + ' (' + alteredValue + ')');

            }

            refreshExampleMap(true);
        },
        //save the map to the database
        saveMap: function(redirect, showMapID) {

            var settings = jQuery.xml2json($mapSettings.Settings);
            var $lat = settings.lattitude;
            var $lng = settings.longitude;
            var $zoom = parseInt(settings.zoom);

            if ($map != null) {
                $lat = $map.getCenter().lat();
                $lng = $map.getCenter().lng();
                $zoom = $map.getZoom();
            }

            var mapOptions = {
                lattitude: $lat,
                longitude: $lng,
                zoom: $zoom,
                markerzoom: jQuery('#markerZoom').val(),
                mapType: jQuery('#mapType').val(),
                backgroundColor: 'FFFFFF',
                draggable: 1,
                clusterpins: 0,
                trafficlayer: 0,
                transitlayer: 0,
                bicyclelayer: 0,
                scrollWheel: 0,
                mapTypeControl: 0,
                panControl: 0,
                rotateControl: 0,
                scaleControl: 0,
                streetViewControl: 1,
                zoomControl: 1,
                mapTypeControl_style: 'DROPDOWN_MENU',
                mapTypeControl_position: 'TOP_RIGHT',
                panControl_position: 'TOP_LEFT',
                rotateControl_position: 'TOP_LEFT',
                scaleControl_position: 'TOP_LEFT',
                streetViewControl_position: 'TOP_LEFT',
                zoomControl_position: 'TOP_LEFT',
                zoomControl_style: 'SMALL',
                polyline_strokecolor: '000000',
                polyline_opacity: '1.0',
                polyline_strokeweight: '1'
            }
            var options = {
                formatOutput: true,
                rootTagName: 'settings'
            };

            jQuery('#divMap').html('');
            document.getElementById('easy2mapmainimage').style.backgroundImage = "none";
            jQuery('#easy2mapslider').css('opacity', '1.0');
            jQuery('#easy2mapslidertext').html('');
            var HTMLToSave = jQuery('#divPreview').html();

            jQuery.ajax({
                type: 'POST',
                url: ajaxurl,
                dataType: 'json',
                data: {
                    mapID: $mapID,
                    mapName: jQuery('#mapName').val() == "" ? "Untitled Photo Map" : jQuery('#mapName').val(),
                    mapTemplateName: jQuery('#MapTemplateName').val(),
                    action: "e2m_img_save_map",
                    mapSettingsXML: jQuery.json2xml(mapOptions, options),
                    parentCSSXML: encodeURIComponent(retrieveParentCSS()),
                    photoCSSXML: encodeURIComponent(retrievePhotoCSS()),
                    mapCSSXML: encodeURIComponent(retrieveMapCSS()),
                    mapHTML: encodeURIComponent(HTMLToSave)
                },
                success: function(mapID) {

                    if (redirect) {

                        if (showMapID) {

                            jQuery('#txtShortCode').val('[easy2mapimg id=' + mapID + ']');
                            jQuery('#mapShortCode').modal({
                                keyboard: false
                            });

                            jQuery('#mapShortCode').on('shown', function() {
                                document.getElementById('txtShortCode').focus();
                                document.getElementById('txtShortCode').select();
                            });

                        } else {

                            window.location = '?page=easy2mapimg&action=viewmaps';

                        }

                        return;
                    }
                    $mapID = mapID;
                    //set the action of the pin upload form to reflect the new mapID!
                    jQuery('#formAddPinIcon').attr('action', '?page=easy2mapimg&action=mappiniconsave&map_id=' + $mapID);
                    jQuery('#formAddPinImage').attr('action', '?page=easy2mapimg&action=mappinimageupload&map_id=' + $mapID);

                },
                error: function(XMLHttpRequest, textStatus, errorThrown) {
                    alert(errorThrown);
                }
            });
        },
        //save the map to the database
        saveMapName: function() {

            jQuery.ajax({
                type: 'POST',
                url: ajaxurl,
                dataType: 'json',
                data: {
                    mapID: $mapID,
                    mapName: jQuery('#mapName').val() == "" ? "Untitled Photo Map" : jQuery('#mapName').val(),
                    action: "e2m_img_save_map_name"
                },
                error: function(XMLHttpRequest, textStatus, errorThrown) {
                    alert(errorThrown);
                }
            });
        }
    }

})();