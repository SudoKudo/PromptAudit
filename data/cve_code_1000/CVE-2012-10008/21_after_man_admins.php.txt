<?php
include("../config.php");
include("../include/common.php");
include("../include/db_connect.php");
include("../include/session.php");

if(isset($_SESSION['root'])) {
	
	if(isset($_REQUEST['action'])) {
		$action = $_REQUEST['action'];
		
		if($action == 'add' && isset($_REQUEST['username']) && isset($_REQUEST['club_id'])) {
			$user_id = getUserId($_REQUEST['username']);
			
			if($user_id !== FALSE) {
				alterAdminClubs($user_id, -1, $_REQUEST['club_id']);
			} else {
				$error = "Username not found.";
			}
		} else if(($action == 'remove' || $action == "Remove") && isset($_REQUEST['id']) && isset($_REQUEST['club_id_orig'])) {
			alterAdminClubs($_REQUEST['id'], $_REQUEST['club_id_orig'], -1);
			$success =  "Admin removed successfully.";
		} else if(($action == 'update' || $action == 'Update') && isset($_REQUEST['id']) && isset($_REQUEST['club_id_orig']) && isset($_REQUEST['club_id'])) {
			alterAdminClubs($_REQUEST['id'], $_REQUEST['club_id_orig'], $_REQUEST['club_id']);
			$success = "Admin updated successfully.";
		}
	}
	
	$clubsList = listClubsIdName();
	$result = mysql_query("SELECT user_groups.user_id, user_groups.`group`, users.username FROM user_groups LEFT JOIN users ON user_groups.user_id = users.id WHERE user_groups.`group` >= '0' ORDER BY user_groups.`group`");
	$adminList = array();
	
	while($row = mysql_fetch_array($result)) {
		array_push($adminList, array($row[0], $row[1], $row[2]));
	}
	
	$parameters = array();
	$parameters['adminList'] = $adminList;
	$parameters['clubsList'] = $clubsList;
	
	if(isset($error)) {
		$parameters['error'] = $error;
	} else if(isset($success)) {
		$parameters['success'] = $success;
	}
	
	get_page_advanced("man_admins", "root", $parameters);
} else {
	header('Location: index.php');
}
?>
