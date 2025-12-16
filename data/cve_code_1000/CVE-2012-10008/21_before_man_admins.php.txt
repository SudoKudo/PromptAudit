<?php
include("../config.php");
include("../include/common.php");
include("../include/db_connect.php");
include("../include/session.php");

if(isset($_SESSION['root'])) {
	
	if(isset($_REQUEST['action'])) {
		$action = $_REQUEST['action'];
		
		if($action == 'add') {
			if($_REQUEST['username'] != "" && $_REQUEST['password'] != "") {
				$result = mysql_query("SELECT id FROM admins WHERE username='" . $_REQUEST['username'] . "'");
				if($row = mysql_fetch_array($result)){
					$error = "Username already in use!";
				} else {
					if($_REQUEST['email'] != "") {
						$result = mysql_query("SELECT id FROM admins WHERE email='" . $_REQUEST['email'] . "'");
						if($row = mysql_fetch_array($result)){
							$error = "Email already in use!";
						} else {
							addAdmin($_REQUEST['username'], $_REQUEST['password'], $_REQUEST['email'], $_REQUEST['club_id']);
							$success = "Admin added successfully!";
						}
					} else {
						addAdmin($_REQUEST['username'], $_REQUEST['password'], $_REQUEST['email'], $_REQUEST['club_id']);
						$success = "Admin added successfully!";
					}
				}
			} else {
				$error = "You need a username and password!";
			}
		} else if($action == 'delete' || $action == 'Delete') {
			$admin_id = escape($_REQUEST['id']);
			mysql_query("DELETE FROM admins WHERE id='$admin_id'");
			$success =  "Admin deleted successfully!";
		} else if($action == 'update' || $action == 'Update') {
			$result = mysql_query("SELECT id FROM admins WHERE username='" . $_REQUEST['username'] . "'");
			if($row = mysql_fetch_array($result)){
				$error = "Username already in use!";
			} else {
				if($_REQUEST['email'] != "") {
					$result = mysql_query("SELECT id FROM admins WHERE email='" . $_REQUEST['email'] . "'");
					if($row = mysql_fetch_array($result)){
						$error = "Email already in use!";
					} else {
						updateAdmin($_REQUEST['id'], $_REQUEST['username'], $_REQUEST['password'], $_REQUEST['email'], $_REQUEST['club_id']);
						$success =  "Admin updated successfully!";
					}
				} else {
					updateAdmin($_REQUEST['id'], $_REQUEST['username'], $_REQUEST['password'], $_REQUEST['email'], $_REQUEST['club_id']);
					$success =  "Admin updated successfully!";
				}
			}
		}
	}
	
	$result = mysql_query("SELECT id, club_id, username, email FROM admins ORDER BY club_id");
	$adminList = array();
	
	while($row = mysql_fetch_array($result)) {
		array_push($adminList, array($row[0], $row[1], $row[2], $row[3]));
	}
	
	if(isset($error)){
		get_page_advanced("man_admins", "root", array('error' => $error, 'adminList' => $adminList));
	} else if(isset($success)){
		get_page_advanced("man_admins", "root", array('success' => $success, 'adminList' => $adminList));
	} else {
		get_page_advanced("man_admins", "root", array('adminList' => $adminList));
	}
} else {
	header('Location: index.php');
}
?>
