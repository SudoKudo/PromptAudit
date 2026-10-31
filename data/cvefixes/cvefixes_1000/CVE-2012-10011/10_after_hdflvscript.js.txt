/**
 * @name          : Script for Hd Flv Player
 * @version	  	  : 1.8
 * @package       : apptha
 * @subpackage    : contus-hd-flv-player
 * @author        : Apptha - http://www.apptha.com
 * @copyright     : Copyright (C) 2011 Powered by Apptha
 * @license	      : GNU General Public License version 2 or later; see LICENSE.txt
 * @Purpose       : For Validation and Sortable Process
 * @Creation Date : Dec 09, 2011
 * @Modified Date : Jul 23, 2012
 * */

var xmlhttp;
var myarray = [];
var myarray1;
function showUser(str, order) {
	xmlhttp = GetXmlHttpObject();
	if (xmlhttp == null) {
		alert("Browser does not support HTTP Request");
		return;
	}
	var url = "../wp-content/plugins/contus-hd-flv-player/process-sortable.php";
	url = url + "?" + order;
	url = url + "&playid=" + str;
	url = url + "&sid=" + Math.random();
	xmlhttp.onreadystatechange = stateChanged;
	xmlhttp.open("GET", url, true);
	xmlhttp.send(null);
}

function stateChanged() {
	if (xmlhttp.readyState == 4) {
		myarray = xmlhttp.responseText;
		myarray1 = myarray.split(",");
		var length1 = myarray1.length - 1;
		var i = 0;
		for (i = 0; i <= length1; i++) {
			document.getElementById('txtHint[' + myarray1[i] + ']').innerHTML = i;
		}

	}
}

function GetXmlHttpObject() {
	if (window.XMLHttpRequest) {
		// code for IE7+, Firefox, Chrome, Opera, Safari
		return new XMLHttpRequest();
	}
	if (window.ActiveXObject) {
		// code for IE6, IE5
		return new ActiveXObject("Microsoft.XMLHTTP");
	}
	return null;
}

// this function is useful to show or display the  HDFLVPlayer Options div when u click on - or + buttons
function hideContentDives(divIdIs, id) {

	var status = document.getElementById(divIdIs).style.display;
	//  alert(status);
	if (status == 'none') {
		document.getElementById(divIdIs).style.display = 'block';
		divStyleDisplaySet(divIdIs, 0);
		document.getElementById(id).className = 'ui-icon ui-icon-minusthick';
	} else {
		document.getElementById(divIdIs).style.display = 'none';
		divStyleDisplaySet(divIdIs, 1);
		document.getElementById(id).className = 'ui-icon ui-icon-plusthick';
	}
}

function divStyleDisplaySet(IdValue, setValue) {
	var xmlhttp;
	var url = "../wp-content/plugins/contus-hd-flv-player/process-sortable.php";
	if (IdValue.length == 0) {

		return;
	}
	if (window.XMLHttpRequest) {// code for IE7+, Firefox, Chrome, Opera, Safari
		xmlhttp = new XMLHttpRequest();
	} else {// code for IE6, IE5
		xmlhttp = new ActiveXObject("Microsoft.XMLHTTP");
	}
	xmlhttp.onreadystatechange = function() {
		if (xmlhttp.readyState == 4 && xmlhttp.status == 200) {
			//  alert(xmlhttp.responseText);
			//document.getElementById("txtHint").innerHTML=xmlhttp.responseText;
		}
	}

	xmlhttp.open("GET", url + '?updatedisplay=1&IdValue=' + IdValue
			+ '&setValue=' + setValue, true);
	xmlhttp.send();
}

function setVideoStatusOff(videoId, status, flag) //click on status image then it exe
{
	//if flag is set 1 then it is playlist status else video status

	var xmlhttp;
	var url = "../wp-content/plugins/contus-hd-flv-player/process-sortable.php";
	//var statusImgPath = document.getElementById('imagepath').value;
	if (window.XMLHttpRequest) {// code for IE7+, Firefox, Chrome, Opera, Safari
		xmlhttp = new XMLHttpRequest();
	} else {// code for IE6, IE5
		xmlhttp = new ActiveXObject("Microsoft.XMLHTTP");
	}
	xmlhttp.onreadystatechange = function() {
		if (xmlhttp.readyState == 4 && xmlhttp.status == 200) {
			imgName = (xmlhttp.responseText);

			//alert(imgName);
			// alert(  document.getElementById('status'+videoId).innerHTML);

			document.getElementById('status' + videoId).innerHTML = imgName;
		}
	}
	if (flag) {
		//	alert( url+'?changeplaylistStatus=1&videoId='+videoId+'&status='+status);
		xmlhttp.open("GET", url + '?changeplaylistStatus=1&videoId=' + videoId
				+ '&status=' + status, true);//for playlist status
	} else {
		xmlhttp.open("GET", url + '?changeVideoStatus=1&videoId=' + videoId
				+ '&status=' + status, true); //for video status
	}

	xmlhttp.send();
} //status fun end hear

/*   manage.php  script                                  */

function savePlaylist(playlistName, mediaId) {
	var name = playlistName.value;
	var pluginUrl = document.getElementById('pluginUrl').value;

	$.ajax({
		type : "GET",
		url : pluginUrl + "/functions.php",
		data : "name=" + name + "&media=" + mediaId,
		success : function(msg) {
			var response = msg.split('##');
			//  alert(msg);
			document.getElementById('playlistchecklist').innerHTML = msg;
		}
	});
}

/**
 * function to validate during adding video files
 * 
 */

function validateInput() {
	document.getElementById('message').style.display = '';
	var YouTubeUrl = document.getElementById('filepath1').value;
	var CustomUrl = document.getElementById('filepath2').value;
	var HdUrl = document.getElementById('filepath3').value;
	var ThumbUrl = document.getElementById('filepath4').value;
	var ThumbPreviewUrl = document.getElementById('filepath5').value;
	var tomatch = /http:\/\/[A-Za-z0-9\.-]{3,}\.[A-Za-z]{3}/;
	if (!tomatch.test(CustomUrl) && (CustomUrl != '')) {
		document.getElementById('message').innerHTML = 'Please enter valid URL';
		return false;
	} else if (!tomatch.test(HdUrl) && (HdUrl != '')) {
		document.getElementById('message').innerHTML = 'Please enter valid Hd Url';
		return false;
	}

	else if (!tomatch.test(ThumbUrl) && (ThumbUrl != '')) {
		document.getElementById('message').innerHTML = 'Please enter valid Thumb Image Url';
		return false;
	} else if (!tomatch.test(ThumbPreviewUrl) && (ThumbPreviewUrl != '')) {
		document.getElementById('message').innerHTML = 'Please enter Preview Image  Url';
		return false;
	} else if (!tomatch.test(YouTubeUrl) && (YouTubeUrl != '')) {
		document.getElementById('message').innerHTML = 'Please enter valid You Tube Url';
		return false;
	}
	if (document.getElementById('btn2').checked == true
			&& document.getElementById('filepath1').value == '') {
		document.getElementById('message').innerHTML = 'Enter Youtube URL';
		return false;
	}
	if (document.getElementById('btn1').checked == true
			&& document.getElementById('f1-upload-form').style.display != 'none') {
		document.getElementById('message').innerHTML = 'Upload Video';
		return false;
	}
	if (document.getElementById('btn3').checked == true
			&& document.getElementById('filepath2').value == '') {
		document.getElementById('message').innerHTML = 'Enter Video URl';
		return false;
	}
	var titlename = document.getElementById('name').value;
	titlename = titlename.trim();
	if (titlename == '') {
		document.getElementById('Errormsgname').innerHTML = 'Please enter the title for video ';
		document.getElementById('name').focus();
		return false;
	}
}

/**
 * function to validate during editing video files
 * 
 */

function edtValidate() {
	
	var edtVideoTitle = document.getElementById('act_name').value;
	var videoUrl = document.getElementById('act_filepath').value;
	var hdUrl = document.getElementById('act_hdpath').value;
	var thumbimgUrl = document.getElementById('act_image').value;
	var previewimgUrl = document.getElementById('act_opimg').value;
	var linkUrl = document.getElementById('act_link').value;
	
	var regexp = /^(((ht|f){1}((tp|tps):[/][/]){1}))[-a-zA-Z0-9@:%_\+.~#!?&//=]+$/;
	
	if (edtVideoTitle.trim() == '') {
		document.getElementById('alert_title').innerHTML = 'Please Enter Video Title';
		return false;
	}else if (videoUrl.trim() == '') {
		document.getElementById('alert_VUrl').innerHTML = 'Please Enter Video URL';
		return false;
	}else if(videoUrl != '' && regexp.test(videoUrl)== false){
		document.getElementById('alert_VUrl').innerHTML = 'Please Enter Valid Video URL';
		return false;
	}else if(hdUrl != '' && regexp.test(hdUrl)== false){ 	 
		document.getElementById('alert_HDURL').innerHTML = 'Please Enter Valid HD Url';
		return false;
	}else if (thumbimgUrl == '') {
		document.getElementById('errmsg_thumbimg').style.display = '';
		document.getElementById('errmsg_thumbimg').innerHTML = 'Please Enter Thumb Image/Url';
		return false;
	}else if (previewimgUrl == '') {
		document.getElementById('errmsg_previewimg').style.display = '';
		document.getElementById('errmsg_previewimg').innerHTML = 'Please Enter Preview Image/Url';
		return false;
	}else if(linkUrl != '' && regexp.test(linkUrl)== false) {
		document.getElementById('alert_linkURL').innerHTML = 'Please Enter Valid Link Url';
		return false;
	}
}

/**
 * function to validate during edit upload video files
 * 
 */

function validateFileExt() {
	var previewImg = document.getElementById('edit_preview').value;
	var thumbImg = document.getElementById('edit_thumb').value;

	if(thumbImg != ''){
		var filext = thumbImg.substring(thumbImg.lastIndexOf(".")+1);					
	}
	
	if(previewImg != ''){
		var filext = previewImg.substring(previewImg.lastIndexOf(".")+1);
	}
	
	filext = filext.toLowerCase();	
	
	if (filext == 'jpg' || filext == 'png' || filext == 'jpeg' || filext == 'gif'){
		return true;
	}else{
		alert("Invalid File Format Selected");
		document.getElementById('edit_preview').value = "";
		document.getElementById('edit_thumb').value = "";
		return false;
	}
}
