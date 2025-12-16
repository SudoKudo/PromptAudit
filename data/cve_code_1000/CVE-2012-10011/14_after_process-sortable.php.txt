<?php
/**
 * @name          : Common functions needed throughout the plugin
 * @version	  	  : 1.8
 * @package       : apptha
 * @subpackage    : contus-hd-flv-player
 * @author        : Apptha - http://www.apptha.com
 * @copyright     : Copyright (C) 2011 Powered by Apptha
 * @license	      : GNU General Public License version 2 or later; see LICENSE.txt
 * @Purpose       : Common functions needed throughout the plugin
 * @Creation Date : Dec 09, 2011
 * @Modified Date : Jul 23, 2012
 * */


/* Used to import plugin configuration */
require_once( dirname(__FILE__) . '/hdflv-config.php');

global $wpdb;

 $pluginDirPath = get_option('siteurl').'/wp-content/plugins/'.dirname(plugin_basename(__FILE__)).'/images';

         $updatedisplay = $_REQUEST['updatedisplay'];
         $changeVideoStatus = $_REQUEST['changeVideoStatus'];
         $changeplaylistStatus = $_REQUEST['changeplaylistStatus'];     
         
if(isset($updatedisplay)){
	
	$IdValue = $_REQUEST['IdValue'];
	$setValue = $_REQUEST['setValue'];
	update_option($IdValue ,$setValue );
	//echo $IdValue.'----'.$setValue;
	exit;
}             
else if(isset($changeVideoStatus))
{
	$videoId = $_REQUEST['videoId'];
	$status  = $_REQUEST['status'];
	$sql = "UPDATE ".$wpdb->prefix."hdflv  SET  is_active = $status WHERE vid = $videoId ";
	$wpdb->query($sql);
	if($status)
	{
		echo "<img  title='deactive' style='cursor:pointer;' onclick='setVideoStatusOff($videoId,0)'  src=$pluginDirPath/hdflv_active.png />";
	}
	else{
		echo "<img  title='active' style='cursor:pointer;' onclick='setVideoStatusOff($videoId,1)'  src=$pluginDirPath/hdflv_deactive.png />";
	}
	
exit;	
}
else if(isset($changeplaylistStatus))
{
	$videoId = $_REQUEST['videoId'];
	$status  = $_REQUEST['status'];
	$sql = "UPDATE ".$wpdb->prefix."hdflv_playlist  SET  is_pactive = $status WHERE pid = $videoId ";
	$wpdb->query($sql);
	if($status)
	{
		echo "<img  title='deactive' style='cursor:pointer;' onclick='setVideoStatusOff($videoId,0,1)'  src=$pluginDirPath/hdflv_active.png />";
	}
	else{
		echo "<img  title='active' style='cursor:pointer;' onclick='setVideoStatusOff($videoId,1,1)'  src=$pluginDirPath/hdflv_deactive.png />";
	}
	
exit;	
}


$title = 'hdflv Playlist';

$pid1 =  filter_input(INPUT_GET, 'playid');
foreach ($_REQUEST['listItem'] as $position => $item) :
    mysql_query("UPDATE $wpdb->prefix" . "hdflv_med2play SET `sorder` = $position WHERE `media_id` = $item and playlist_id=$pid1 ");
endforeach;

$tables = $wpdb->get_results("SELECT vid FROM $wpdb->prefix" . "hdflv LEFT JOIN " . $wpdb->prefix . "hdflv_med2play ON (vid = media_id) WHERE (playlist_id = '$pid1') ORDER BY sorder ASC, vid ASC");


if ($tables) {
    foreach ($tables as $table) {
        $playstore1 .= $table->vid . ",";
    }
}
?>