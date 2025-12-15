var easy2map_imgmappin_functions = (function(){
    
    /*clear the array that contains all pins located on the map*/
    clearPinArray = function(){
        
        if ($pinsArray) {
            for (i in $pinsArray) {
                $pinsArray[i].setMap(null);
                $pinsArray[i].setAnimation(null);
            }
        }
        if ($pinsArray) $pinsArray.length = 0;
        $selectedPin = null;
        
    };
    
    /*add the selected pin onto the Google map*/
    addPinToMap = function (objPointDetails){

        this.selectedMapPoint = objPointDetails;

        var marker = new google.maps.Marker({
            position	: new google.maps.LatLng(this.selectedMapPoint.lattitude, this.selectedMapPoint.longitude),
            draggable	: true,
            map		: $map,
            title           : this.selectedMapPoint.title.replace(/\\/gi, ''),
            ID              : this.selectedMapPoint.ID,
            icon            : this.selectedMapPoint.icon,
            settings        : this.selectedMapPoint.settings,
            small           : this.selectedMapPoint.small,
            medium          : this.selectedMapPoint.medium,
            large           : this.selectedMapPoint.large,
            pinHTML         : this.selectedMapPoint.pinhtml,
            pinText         : this.selectedMapPoint.pintext,
            visible         : false
        });
        
        $pinsArray.push(marker);
        //insert the pin onto the map here
        google.maps.event.addListener(marker, "dragend", function (mEvent) {
            $latlng = mEvent.latLng;
            showLatLong();
            updateMapPinLocation(marker.ID);
        });
        
        //show the pin's info window when it is clicked
        google.maps.event.addListener(marker, "click", function (mEvent) {
            
            var pinContent = "";
            
            var lines = marker.pinHTML.split('\n');
            for(var i = 0; i < lines.length; i++){
                if (i > 0) pinContent += "<br>";
                pinContent += lines[i];
            }
            
        //var infoWindow = new google.maps.InfoWindow();
        //infoWindow.setContent(pinContent);
        //infoWindow.open(marker.map, marker);
        });
    };
    
    clearTextOfAllFormatting = function(html){
        
        //remove MS Word formatting
        html = replaceAll(html, "&quot;Arial&quot;", "Arial");
        html = replaceAll(html, "&quot;Times New Roman&quot;", "Arial");
        html = replaceAll(html, "&quot;sans-serif&quot;", "sans-serif");
        html = replaceAll(html, 'class="MsoNormal"', '');

        html = html.replace(/ – /g, " - ");

        //gmail does not render line-height correctly
        html = replaceAll(html, "line-height:", "min-height:");

        if (html.indexOf('<p') != -1){
            html = replaceAll(html, "'", '&#39;');
        }

        html = replaceAll(html, '<p>', '<p style="margin:0; padding:0;">');
        html = replaceAll(html, '<p style="text-align: left;">', '<p style="text-align: left;margin:0; padding:0;">');
        html = replaceAll(html, '<p style="text-align: right;">', '<p style="text-align: left;margin:0; padding:0;">');
        html = replaceAll(html, '<p style="text-align: center;">', '<p style="text-align: left;margin:0; padding:0;">');

        //remove MS Word formatting
        if (html.indexOf('[endif]') != -1){
            html = html.substring(html.lastIndexOf('[endif]') + 10);
        }
        
        return html;
    };
    
    //function used as object for saving details of pins in a loop
    listedMapPin = function(objPinDetails){
        this.pinDetails = objPinDetails;
    };
    
    //set the current pins image
    setPinImage = function (img){
        jQuery('#draggable').attr('src', jQuery(img).attr('src'));
        jQuery('#mapPinIconList').modal('hide');
        
        if ($pinsArray) {
            for (i in $pinsArray) {
                
                if (!!$selectedPin == false) continue;
                if (typeof $pinsArray[i].ID == "undefined" || typeof $selectedPin.ID == "undefined") continue;
                if ($pinsArray[i].ID == $selectedPin.ID) $pinsArray[i].setIcon(jQuery(img).attr('src'));
            }
        }
    };
    
    //show lat/lng of current pin
    showLatLong = function (){
        jQuery('#latLongParent').show();
        jQuery('#divLatLong').html('Position of Pin: ' + $latlng);
    };
    
    //update the lat lng of the current pin after it is dragged and dropped
    updateMapPinLocation = function(mapPinID){
               
        jQuery.ajax({
            type : 'POST',
            url : ajaxurl,
            dataType : 'json',
            data: {
                mapPointID : mapPinID,
                latLong : $latlng + '',
                action : "e2m_img_update_map_pin_location"
            }
        });
    };
       
    return{
        
        //prepare the front-end to allow the user to add a new marker to the map
        addNewMapMarker : function(){
            
            jQuery('.fileupload').fileupload('clear');
            jQuery('#AddMarkerOrSave').hide();
            jQuery('#tblAddMapMarker').show();
                        
        },
        
        //hide all edit controls from view
        cancelSaveMapPin : function (){
            
            jQuery('#pinDescriptionParent').hide();
            jQuery('#divAddressSearch').hide();
            jQuery('#divDrag').hide();
            jQuery('#divDrag2').hide();
            jQuery('#btnCancelPin').hide();
            jQuery('#pinImageUploadParent').show();
            jQuery('#pinImageParent').hide();
            
            jQuery('#AddMarkerOrSave').hide();
            jQuery('#tblAddMapMarker').hide();
            
            jQuery('#address').attr('placeholder', "Enter address where this picture was taken");
            
            document.getElementById('MapTemplateName').style.visibility = 'visible';
            
            var proVersion = !!jQuery("#photoSize").attr("proVersion");
            if (proVersion == false){
                document.getElementById('mapSize').style.visibility = 'hidden';
                document.getElementById('photoSize').style.visibility = 'hidden';
                document.getElementById('mapType').style.visibility = 'hidden';
                document.getElementById('markerZoom').style.visibility = 'hidden';
            } else {
                document.getElementById('mapSize').style.visibility = 'visible';
                document.getElementById('photoSize').style.visibility = 'visible';
                document.getElementById('mapType').style.visibility = 'visible';
                document.getElementById('markerZoom').style.visibility = 'visible';
            }
            document.getElementById('easy2mapmainimage').style.backgroundImage = "none";
            
            jQuery('#draganddrop').show();
            jQuery('#AddEditPinTitle').html('Add New Photo').show();
            jQuery('#divPinAddEditParent').hide();
            jQuery('#easy2mapslidertext').html('').hide();
            
            jQuery('#pinDescription').data("wysihtml5").editor.clear();
            
            jQuery('#btnDeletePin').hide();
            jQuery('#btnSavePin').hide();
            jQuery('#latLongParent').hide();
            jQuery('#draggable').attr("src", $mapSettings.DefaultPinImage);
            if ($selectedPin) $selectedPin.setAnimation(null);
            $selectedPin = null;
            
            //prepare the pin for dragging onto the map
            easy2map_imgmappin_functions.setIconDraggable();
            
            jQuery('td [id ^= imageTd]').removeClass('highlighted');
            jQuery('td [id ^= nameTd]').removeClass('highlighted');
            
            //remove the current pin from the public array
            if ($pinsArray) {
                for (i in $pinsArray) {
                    if ($pinsArray[i].ID == 0) {
                        $pinsArray[i].setMap(null);
                        $pinsArray[i].setAnimation(null);
                        $pinsArray[i].setVisible(false);
                        $pinsArray.splice(i, 1);
                    }
                }
            }
            
            jQuery('tr [id ^=divPinInstructions]').show();
            jQuery('#draganddrop').show();
            $mapPinID = 0;
        },
        
        //allow the user to change the pin template
        changeMapPinTemplate : function(){
    
            var templateID = parseInt(jQuery("#MapPinTemplateName").val());
    
            for(var t = 0; t < $arrTemplates.length; t++){
        
                var template = $arrTemplates[t];
                if (parseInt(template.ID) == templateID){
                    jQuery('#MapTemplateExampleImg').html(template.TemplateHTML);
                }        
            }
        },
        
        //deleting map pin
        deleteSelectedPoint : function (){

            if (!confirm('Are you sure you wish to delete this marker? This action is not reversible!')) return;
            
            jQuery.ajax({
                type : 'POST',
                url : ajaxurl,
                dataType : 'json',
                data: {
                    MapPointID : $mapPinID,
                    action: 'e2m_img_delete_map_point'
                },
                success : function(returnData){

                    if (returnData.length > 0){
                        alert(returnData);
                        return;
                    }
                    
                    clearPinArray();
                    if ($pinsArray) $pinsArray.length = 0;
                    easy2map_imgmappin_functions.retrieveMapPoints();
                },
                error : function(XMLHttpRequest, textStatus, errorThrown) {
                    if (errorThrown.length > 0) alert(errorThrown);
                }
            });
        },
        
        //prepare a pin item for editing
        editPinItem : function(index){
            
            for (i = 0; i < $pinsArray.length; i++){
                $pinsArray[i].setVisible(false);
            }
            
            var pinDetails = $markersArray[index].pinDetails;
            $latlng = new google.maps.LatLng(pinDetails.lattitude, pinDetails.longitude);
            $selectedPin = $pinsArray[index];
            $selectedPin.setVisible(true);
            showLatLong();
            
            $selectedPin.setAnimation(google.maps.Animation.BOUNCE);
            setTimeout(function(){
                $selectedPin.setAnimation(null);
            }, 1500);
            $map.setCenter($latlng);            
            
            jQuery('td [id ^= imageTd]').removeClass('highlighted');
            jQuery('td [id ^= nameTd]').removeClass('highlighted');
            
            jQuery('#imageTd' + index).addClass('highlighted');
            jQuery('#nameTd' + index).addClass('highlighted');
            document.getElementById('mapSize').style.visibility = 'hidden';
            document.getElementById('photoSize').style.visibility = 'hidden';
            document.getElementById('mapType').style.visibility = 'hidden';
            document.getElementById('markerZoom').style.visibility = 'hidden';
            document.getElementById('MapTemplateName').style.visibility = 'hidden';  
            
            jQuery('#pinDescriptionParent').show();
            jQuery('#divAddressSearch').show();
            jQuery('#address').attr('placeholder', "Change Photo Marker's Location");
            
            jQuery('#AddMarkerOrSave').hide();
            jQuery('#tblAddMapMarker').show();
            
            jQuery('#pinImagePreview').attr('src', pinDetails.large); 
            jQuery('#pinImageUploadParent').hide();
            //jQuery('#pinImageParent').show();
            
            jQuery('#draganddrop').hide();
            jQuery('#btnCancelPin').show();
            jQuery('#AddEditPinTitle').html('Edit Photo Details').show();
            jQuery('#btnUploadIcon').html('Change Icon');
            jQuery('#divDrag').hide();
            jQuery('#divPinAddEditParent').show();
            
            jQuery('#pinName').val(pinDetails.title.replace(/\\/gi, ''));
            jQuery('#pinDescription').data("wysihtml5").editor.setValue(pinDetails.pintext);
            
            jQuery('#small').val(pinDetails.small);
            jQuery('#medium').val(pinDetails.medium);
            jQuery('#large').val(pinDetails.large);
            jQuery('#easy2mapmainimage').css({
                'background-image' : 'url(' + pinDetails.large + ')', 
                'background-repeat': 'no-repeat', 
                'background-position': 'center'
            }).fadeIn();
            jQuery('#easy2mapslidertext').html(pinDetails.pintext).show();
                                    
            
            $mapPinID = pinDetails.ID;
            jQuery('#btnDeletePin').show();
            jQuery('#btnSavePin').show();
            jQuery('tr [id ^=divPinInstructions]').hide();
            jQuery('#draggable').attr('src', pinDetails.icon);
            easy2map_imgmappin_functions.setIconNotDraggable();
            easy2map_imgmap_functions.disableHover();
            
        },
        
        hidePreviewPage : function (){
            jQuery('#divMultipleLocations').fadeOut();
        },
        
        imageNotSuccessfullyUploaded : function (){
            
            if (document.getElementById('pinimage').value != ""){
                jQuery('#photoUploadError').modal();    
                notBusy();
            }
            
        },
        
        imageSuccessfullyUploaded : function (smallImage, mediumImage, largeImage, lat, lng){
            
            jQuery('#easy2mapmainimage').css({
                'background-image' : 'url(' + largeImage + ')', 
                'background-repeat': 'no-repeat', 
                'background-position': 'center'
            });
                        
            for (i = 0; i < $pinsArray.length; i++){                
                $pinsArray[i].setVisible(false);
            }
            
            //jQuery('#pinImagePreview').attr('src', largeImage); 
            jQuery('#small').val(smallImage);
            jQuery('#medium').val(mediumImage);
            jQuery('#large').val(largeImage);
            jQuery('#pinImageUploadParent').hide();
            document.getElementById('mapSize').style.visibility = 'hidden';
            document.getElementById('photoSize').style.visibility = 'hidden';
            document.getElementById('mapType').style.visibility = 'hidden';
            document.getElementById('markerZoom').style.visibility = 'hidden';
            document.getElementById('MapTemplateName').style.visibility = 'hidden';
            jQuery('#AddEditPinTitle').html('Specify Photo\'s Location');
            jQuery('#btnSavePin').hide();
            jQuery('#btnDeletePin').hide();
            jQuery('#btnCancelPin').show();
            jQuery('#divPinAddEditParent').show();
            $selectedPin = null;
            //jQuery('#draggable').attr('src', smallImage);
            
            if (lat === 0 && lng === 0){ 
                
                jQuery('#divAddressSearch').show();
                jQuery('#divDrag').show();
                jQuery('#divDrag2').show();
                           
            } else {
                easy2map_imgmappin_functions.SetPinPosition(lat, lng); 
            }
            
            easy2map_imgmap_functions.disableHover();
            jQuery('#easy2mapslidertext').html('').hide();
            jQuery('#pinimage').val('');            
            notBusy();
            
        },
        
        //retrieve all pin icons associated with this map
        openImagesDirectory : function (selectedImage){
            
            jQuery.ajax({
                type            : 'POST',
                url             : ajaxurl,
                dataType        : 'json',
                data: {
                    mapID : $mapID,
                    action : 'e2m_img_retrieve_pin_icons'
                },
                success : function(returnData){

                    jQuery('#tblPinImages').find('tr').remove();
                    var iCounter = 0;
                    for (var i = 0; i < returnData.length; i++){
                        if (iCounter % 6 == 0){
                            var tr = document.createElement('tr');
                            document.getElementById('tblPinImages').appendChild(tr);
                        }

                        var imageTd                 = document.createElement('td');
                        imageTd.align               = "center";
                        imageTd.style.borderColor = "#FFFFFF";
                        imageTd.style.padding       = "2px";
                        if (returnData[i] == selectedImage){
                            imageTd.style.borderColor = "#EBEBEB";
                            imageTd.style.borderWidth = "2px";
                            imageTd.style.borderStyle = "solid";
                            imageTd.style.borderRadius  = "3px"
                        }

                        var image = document.createElement('img');
                        image.style.cursor = "pointer";
                        image.setAttribute("onClick", "easy2map_imgmappin_functions.setMapPinImage(this)");
                        
                        image.src = returnData[i];
                        imageTd.appendChild(image);
                        tr.appendChild(imageTd);
                        iCounter += 1;
                    }
                    
                    jQuery('#mapPinIconList').modal();
                },
                error : function(XMLHttpRequest, textStatus, errorThrown) {
                    alert(errorThrown);
                }
            });
        },
        
        //run this function when a pin is dropped onto a map - setup controls for creating pin
        placePin : function (location, bounce) {
            
            for (i = 0; i < $pinsArray.length; i++){
                $pinsArray[i].setVisible(false);
            }
            
            var marker = new google.maps.Marker({
                position    : location,
                ID          : 0,
                draggable   : true,
                bouncy      : true,
                title       : 'Click on icon to edit details',
                map         : $map,
                icon        : jQuery('#draggable').attr('src')
            });
            
            $latlng = marker.position;
            $pinsArray.push(marker);
            $selectedPin = $pinsArray[$pinsArray.length - 1];
            showLatLong();
            
            if (!!bounce){
                $selectedPin.setAnimation(google.maps.Animation.BOUNCE);
                setTimeout(function(){
                    $selectedPin.setAnimation(null);
                }, 1500);
            }
            
            jQuery('#pinDescriptionParent').show();
            jQuery('#divAddressSearch').hide();
            document.getElementById('mapSize').style.visibility = 'hidden';
            document.getElementById('photoSize').style.visibility = 'hidden';
            document.getElementById('mapType').style.visibility = 'hidden';
            document.getElementById('markerZoom').style.visibility = 'hidden';
            document.getElementById('MapTemplateName').style.visibility = 'hidden';
            
            jQuery('#draganddrop').hide();
            jQuery('#btnCancelPin').show();
            jQuery('#AddEditPinTitle').hide();
            jQuery('#btnUploadIcon').html('Change Icon');
            jQuery('#address').attr('placeholder', "Change Marker's Location");
            jQuery('#divDrag').hide();
            jQuery('#divPinAddEditParent').show();
            
            jQuery('tr [id ^=divPinInstructions]').hide();
            jQuery('#pinDescription').focus();
                        
            jQuery('#btnSavePin').show();
            easy2map_imgmappin_functions.setIconNotDraggable();
            
            google.maps.event.addListener(marker, "dragend", function (mEvent) {
                $latlng = mEvent.latLng;
                showLatLong();
            });
            
            google.maps.event.addListener(marker, "click", function (mEvent) {
                $latlng = mEvent.latLng;
                showLatLong();
            });
            
            easy2map_imgmap_functions.disableHover();
            
        },
        
        //retrieve all points associated with this map
        retrieveMapPoints : function (){
            
            busy();
            
            var data = {
                action: 'e2m_img_retrieve_map_points',
                MapID : $mapID
            };
            
            //clear all controls for blank slate
            easy2map_imgmappin_functions.cancelSaveMapPin();
            easy2map_imgmap_functions.disableHover();
        
            jQuery.ajax({
                type: "POST",
                url: ajaxurl,
                data: data,
                dataType : 'json',
                success: function(returnData) {
                    
                    jQuery('#tblMapMarkers').show().find('tr').remove();
                    jQuery('#Easy2MapSliderParent').show().find('li').remove();
                    
                    var noPinsFound = false;
                    
                    if (typeof returnData == "undefined" || typeof returnData == "null") noPinsFound = true;
                    if (!returnData) noPinsFound = true;
                    if (returnData.length == 0)  noPinsFound = true;
                    
                    if (noPinsFound){
                        //if no pins are found, prompt the user to add a new pin
                        jQuery('#AddMarkerOrSave').hide();
                        jQuery('#tblAddMapMarker').show();
                        easy2mapimg_functions.noPinsLoaded();
                        notBusy();
                        return;
                    } else {
                        //show all pins associated with the map
                        jQuery('#AddMarkerOrSave').show();
                        jQuery('#tblAddMapMarker').hide();
                    }
                    
                    if ($markersArray) $markersArray.length = 0;
                    clearPinArray();
                                                           
                    for(var t = 0; t < returnData.length; t++){
                        
                        var arrLatLng = replaceAll(replaceAll(replaceAll(returnData[t].LatLong, ' ', ''), '(', ''), ')', '').split(',');
                        var objMapPoint = {
                            lattitude : arrLatLng[0],
                            longitude : arrLatLng[1],
                            ID : returnData[t].ID,
                            title : returnData[t].Title,
                            icon : returnData[t].ImageURL,
                            settings : returnData[t].Settings,
                            small : returnData[t].PinImageSmall,
                            medium : returnData[t].PinImageMedium,
                            large : returnData[t].PinImageLarge,
                            pinhtml : returnData[t].MapPinHTML,
                            pintext : returnData[t].MapPinText
                        }
                        
                        $markersArray.push(new listedMapPin(objMapPoint));
                    }
                    
                    var sliderImages = [];
                    for (var i = 0; i < $markersArray.length; i++){
                        
                        var selectedListItem = $markersArray[i].pinDetails;
                        addPinToMap(selectedListItem);
                        
                        if (document.getElementById('Easy2MapSliderParent')){
                            var li = document.createElement('li');
                            li.className = "easy2mapslide";
                            
                            li.setAttribute("sliderID", selectedListItem.ID);
                            li.setAttribute("onClick", "easy2mapimg_functions.clickPinItem(" + selectedListItem.ID + ")");
                            document.getElementById('Easy2MapSliderParent').appendChild(li);
                            sliderImages.push(selectedListItem.medium);
                        }
                       
                        var tr = document.createElement('tr');
                        document.getElementById('tblMapMarkers').appendChild(tr);
                       
                        var imageTd = document.createElement('td');
                        imageTd.id = "imageTd" + i;
                        imageTd.align = "center";
                        imageTd.style.textAlign = "center";
                        var image = document.createElement('img');
                        image.style.cursor = "pointer";
                        image.setAttribute("onClick", "easy2map_imgmappin_functions.editPinItem(" + i + ")");
                        image.src = selectedListItem.icon;
                        imageTd.style.minWidth = '10px';
                        imageTd.style.verticalAlign = 'middle';
                        imageTd.appendChild(image);
                        
                        var imageTd2 = document.createElement('td');
                        imageTd2.id = "imageTd2" + i;
                        imageTd2.align = "center";
                        imageTd2.style.textAlign = "center";
                        var image2 = document.createElement('img');
                        image2.border = "1px solid #EBEBEB";
                        image2.style.cursor = "pointer";
                        image2.setAttribute("onClick", "easy2map_imgmappin_functions.editPinItem(" + i + ")");
                        image2.src = selectedListItem.medium;
                        imageTd2.title = selectedListItem.title.replace(/\\/gi, '');
                        imageTd2.appendChild(image2);
                        imageTd2.style.width = '60%';
                        
                        var editTd = document.createElement('td');
                        editTd.id = "editTd" + i;
                        editTd.style.minWidth = '10%';
                        editTd.style.textAlign = 'center';
                        var editLink = document.createElement('a');
                        editLink.innerText = 'edit';
                        editLink.textContent = 'edit';
                        editLink.href = '#';
                        editLink.setAttribute('className', 'smallE2MLink');
                        editLink.setAttribute('onclick', "easy2map_imgmappin_functions.editPinItem(" + i + ")");
                        editTd.appendChild(editLink);
                        
                        tr.appendChild(imageTd);
                        tr.appendChild(imageTd2);
                        tr.appendChild(editTd);
                       
                    }
                    
                    if (sliderImages.length > 0){
                        jQuery.preloadImages(sliderImages, function initSliderImages(){
                            jQuery('#easy2mapslider').imgSlider(sliderImages);
                        });
                    }
                    
                    jQuery('#tblMapMarkers').removeClass('table-striped').addClass('table-striped');
                    
                    jQuery("#Easy2MapSliderParent li:first").each(function(){
                        easy2mapimg_functions.clickPinItem(jQuery(this).attr('sliderID'));
                    });
                    
                    if ($markersArray.length > 1) {
                        easy2map_imgmap_functions.enableHover();
                    } else {
                        jQuery("#easy2mapslider").hide();
                    }
                    
                    notBusy();
                },
                error : function(XMLHttpRequest, textStatus, errorThrown) {
                    notBusy();
                }
            });
        },
        
        //save map pin to database
        saveMapPin : function (){
            
            var pinText = clearTextOfAllFormatting(jQuery('#pinDescription').val());
            
            var pinHTML = "<div style='padding:3px;margin:5px;border:1px solid #EBEBEB' align='center'><img src='" + jQuery('#large').val() + "'>";
            if (pinText.length > 0) pinHTML += "<div style='text-align:left;margin:0px;padding:0px;'>" + pinText + "</div>";
            pinHTML += "</div>";
            
            busy();
            
            //convert pin settings to XML
            //var pinSettings = {
            //    load : jQuery('#PinLoad option:selected').val(),
            //    url : jQuery('#PinURL').val()
            //}
            //var options                             = { formatOutput: true, rootTagName: 'settings'};
            //var PinSettingsXML                      = jQuery.json2xml(pinSettings, options);
            
            jQuery.ajax({
                type 	: 'POST',
                url 	: ajaxurl,
                dataType : 'json',
                data: {
                    mapPointID : $mapPinID,
                    action : "e2m_img_save_map_pin",
                    latLong : $latlng + '',
                    icon : jQuery('#draggable').attr('src'), 
                    pinTitle : '',
                    small : jQuery('#small').val(),
                    medium : jQuery('#medium').val(),
                    large : jQuery('#large').val(),
                    pinSettingsXML : '',
                    pinHTML : pinHTML,
                    pinText : pinText,
                    mapID : $mapID
                },
                success : function(mapPinID){
                    easy2map_imgmappin_functions.retrieveMapPoints();
                    $selectedPin = null;
                },
                error : function(XMLHttpRequest, textStatus, errorThrown) {
                    alert(errorThrown);
                    notBusy();
                }
            });
            
        },
        
        setCurrentPosition : function (lat,lng){
            var location = new google.maps.LatLng(lat, lng);
            $latlng = location;
        },
        
        //save default image associated with map pins
        setMapPinImage :  function (img){
        
            jQuery.ajax({
                type : 'POST',
                url : ajaxurl,
                dataType : 'json',
                data: {
                    MapID : $mapID,
                    PinImage : encodeURIComponent(jQuery(img).attr('src')),
                    action : "e2m_img_save_default_pin_image"
                },
                success : function(returnImage){
                    jQuery('#draggable').attr('src', jQuery(img).attr('src'));
                    jQuery('#mapPinIconList').modal('hide');
                    $mapSettings.DefaultPinImage = returnImage;
                    setPinImage(img);
                },
                error : function(XMLHttpRequest, textStatus, errorThrown) {
                    alert(errorThrown);
                }
            });

        },
        
        //set the pin's lat-lng position
        SetPinPosition : function (lat,lng){
            
            var location = new google.maps.LatLng(lat, lng);
            $latlng = location;
            if ($selectedPin == null) {
                
                easy2map_imgmappin_functions.placePin(location, true);
                
                //set map center, and save settings to map settings
                $map.setCenter(location);
                $map.setZoom(parseInt(jQuery('#markerZoom').val()));
                var settings = jQuery.xml2json($mapSettings.Settings);
                settings.lattitude = lat;
                settings.longitude = lng;
                settings.zoom =  $map.getZoom();

                var options = {
                    formatOutput: true, 
                    rootTagName: 'settings'
                };
                $mapSettings.Settings = jQuery.json2xml(settings, options);
                
                
            }
            else $selectedPin.setPosition(location);
            
            setTimeout("jQuery('#address').val('')", 1500); 
        },
        
        //prepare the icon to be dragged onto the map
        setIconDraggable : function(){
            
            jQuery("#draggable").css('cursor', 'move');
            jQuery("#draggable").draggable({                    
                appendTo: '#bodyTag',
                scroll: false,
                helper: 'clone',
                stop: function(e) {
                    
                    var bounds = $map.getBounds();
                    var latLngSouthW = bounds.getSouthWest();
                    var latLngNorthE = bounds.getNorthEast();
                    var position = jQuery('#divMap').offset();
                    var point = new google.maps.Point(e.pageX - position.left,e.pageY -position.top + 22);
                    var item = $overlay.getProjection().fromContainerPixelToLatLng(point);
                    if (latLngSouthW.lng() > 0 && (item.lng() > 0 && item.lng() < latLngSouthW.lng())) return;
                    if (latLngSouthW.lng() < 0 && (item.lng() < 0 && item.lng() < latLngSouthW.lng())) return;
                    
                    if (latLngNorthE.lng() > 0 && (item.lng() > 0 && item.lng() > latLngNorthE.lng())) return;
                    if (latLngNorthE.lng() < 0 && (item.lng() < 0 && item.lng() > latLngNorthE.lng())) return;
                    
                    easy2map_imgmappin_functions.placePin(item);
                }
                
            });
            
        },
        
        setIconNotDraggable : function(){
            jQuery('#draggable').css('cursor', 'default').draggable('destroy');
        },

        //verify that the pin icon is a valid image file
        uploadPinIcon : function (){
                
            var validateFileType = checkFileExtensionSilent(document.getElementById('pinicon'));
            if (validateFileType != ''){
                alert('Invalid file, only the following image types are allowed: ' + validateFileType + '. Please upload a different image.');
                return;
            }
            document.formAddPinIcon.submit();
        },
        
        //verify that the pin icon is a valid image file
        uploadPinPicture : function (){
            
            if (document.getElementById('pinimage').value === "") return;
            var bContinue = true;
                
            var validateFileType = checkFileExtensionSilent(document.getElementById('pinimage'));
            if (validateFileType != ''){
                alert('Invalid file, only the following image types are allowed: ' + validateFileType + '. Please upload a different image.');
                bContinue = false;
                return;
            }
            
            if (bContinue == true){
                busy();
                document.formAddPinImage.submit();
            }
        }
    }
    
})();