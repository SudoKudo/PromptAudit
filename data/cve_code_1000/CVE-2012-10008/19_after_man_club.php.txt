<?php
include("../config.php");
include("../include/common.php");
include("../include/db_connect.php");
include("../include/session.php");

if(isset($_SESSION['admin'])) {
	$club_id = $_SESSION['admin_club_id'];
	$user_id = $_SESSION['user_id'];
	
	if($club_id != 0) {
		if(isset($_REQUEST['description']) && isset($_REQUEST['view_time']) && isset($_REQUEST['open_time']) && isset($_REQUEST['close_time'])) {
			$description = escape($_REQUEST['description']);
			$view_time = strtotime($_REQUEST['view_time']);
			$open_time = strtotime($_REQUEST['open_time']);
			$close_time = strtotime($_REQUEST['close_time']);
			$num_recommend = escape($_REQUEST['num_recommend']);

			mysql_query("UPDATE clubs SET description='$description', view_time='$view_time', open_time='$open_time', close_time='$close_time', num_recommend='$num_recommend' WHERE id='$club_id'");
			$success = "Club updated successfully.";
		}
		
		$result = mysql_query("SELECT name, description, view_time, open_time, close_time, num_recommend FROM clubs WHERE id='$club_id'");
	
		if($row = mysql_fetch_array($result)) {
			$parameters = array('club_name' => $row['name'], 'description' => $row['description'], 'view_time' => $row['view_time'], 'open_time' => $row['open_time'], 'close_time' => $row['close_time'], 'num_recommend' => $row['num_recommend']);
			
			if(isset($error)) {
				$parameters['error'] = $error;
			} else if( isset($success) ){
				$parameters['success'] = $success;
			} else if( isset($info) ){
				$parameters['info'] = $info;
			} else if( isset($warning) ){
				$parameters['warning'] = $warning;
			}
			
			get_page_advanced("man_club", "admin", $parameters);
		} else {
			get_page_advanced("message", "admin", array('message' => "Error: your club cannot be found in the clubs table.", 'title' => "Manage Club"));
		}
	} else {
			get_page_advanced("message", "admin", array('message' => "Error: general application does not have club settings.", 'title' => "Manage Club"));
	}
} else {
	header('Location: index.php?error=' . urlencode("You are not logged in!"));
}
