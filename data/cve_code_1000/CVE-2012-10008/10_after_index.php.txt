<?php
include("../config.php");
include("../include/common.php");
include("../include/db_connect.php");
include("../include/session.php");

if(isset($_REQUEST['error'])) {
	$error = $_REQUEST['error'];
}

if(!isset($_SESSION['admin']) && (isset($_SESSION['user_id']) || isset($_REQUEST['username'])) && isset($_REQUEST['password']) && isset($_REQUEST['club'])) {
	if(!isset($_SESSION['user_id'])) {
		//log in first
		$loginResult = checkLogin($_REQUEST['username'], $_REQUEST['password']);
		
		if($result >= 0) {
			$_SESSION['user_id'] = $loginResult;
		} else if($result == -2) {
			$error = "Please try again later (you are locked out for too many failed attempts).";
		} else if($result == -3) {
			$error = "Login and registration are currently disabled.";
		} else if($result == -1) {
			$error = "Login information is not correct.";
		} else {
			$error = "Internal error!";
		}
	}
	
	//only continue if we haven't failed already
	if(isset($_SESSION['user_id'])) {
		$attempt_club_id = escape(intval($_REQUEST['club']));
		$checkResult = checkAdminLogin($_SESSION['user_id'], $_REQUEST['password'], $attempt_club_id);
		
		if($checkResult === TRUE) {
			$_SESSION['admin'] = true;
			$_SESSION['admin_club_id'] = $attempt_club_id;
			
			//make sure a admin_notes_settings entry exists for this user
			$result = mysql_query("SELECT COUNT(*) FROM admin_notes_settings WHERE user_id = '" . $_SESSION['user_id'] . "'");
			$row = mysql_fetch_row($result);
		
			if($row[0] == 0) {
				mysql_query("INSERT INTO admin_notes_settings (user_id, box_enabled, cat_enabled, comment_enabled) VALUES ('" . $_SESSION['user_id'] . "', '0', '0', '0')");
			}
		} else if($checkResult === -1) {
			$error = "Login information is not correct.";
		} else if($checkResult === -2) {
			$error = "Please try again later (you are locked out for too many failed attempts).";
		} else if($checkResult === 1) {
			$error = "Invalid club specified.";
		}
	}
} else if(isset($_REQUEST['action']) && isset($_SESSION['admin'])) {
	if($_REQUEST['action'] == 'logout') {
		$success = "You are now logged out of the club administration area.";
		unset($_SESSION['admin']);
		unset($_SESSION['admin_club_id']);
	}
}

$parameters = array();

if(isset($error)) {
	$parameters['error'] = $error;
} else if(isset($success)) {
	$parameters['success'] = $success;
}

if(isset($_SESSION['admin'])) {
	get_page_advanced("index", "admin", $parameters);
} else {
	if(isset($_SESSION['user_id'])) {
		$parameters['user_loggedin'] = true;
		$parameters['clubs'] = getAdminClubs($_SESSION['user_id']);
	} else {
		$parameters['user_loggedin'] = false;
		
		//list normal clubs, and general application
		$parameters['clubs'] = listClubsIdName();
		$parameters['clubs'][0] = 'General application';
	}
	
	get_page_advanced("index_login", "admin", $parameters);
}
?>
