<?php
include("../include/common.php");
include("../config.php");
include("../include/db_connect.php");
include("../include/session.php");

$parameters = array();

if(isset($_REQUEST['action']) && isset($_SESSION['root'])) {
	if($_REQUEST['action'] == 'logout') {
		unset($_SESSION['root']);
		$parameters['success'] = "You are now logged out of the site administration area.";
	}
} else if(!isset($_SESSION['root']) && (isset($_SESSION['user_id']) || isset($_REQUEST['username'])) && isset($_REQUEST['password'])) {
	if(!isset($_SESSION['user_id'])) {
		//log in first
		$loginResult = checkLogin($_REQUEST['username'], $_REQUEST['password']);
		
		if($loginResult >= 0) {
			$_SESSION['user_id'] = $loginResult;
		} else if($loginResult == -2) {
			$parameters['error'] = "Please try again later (you are locked out for too many failed attempts).";
		} else if($loginResult == -3) {
			$parameters['error'] = "Login and registration are currently disabled.";
		} else if($loginResult == -1) {
			$parameters['error'] = "Login information is not correct.";
		} else {
			$parameters['error'] = "Internal error!";
		}
	}
	
	//only continue if we haven't failed already
	if(isset($_SESSION['user_id'])) {
		$checkResult = checkRootLogin($_SESSION['user_id'], $_REQUEST['password']);
		
		if($checkResult === TRUE) {
			$_SESSION['root'] = true;
		} else if($checkResult === -1) {
			$parameters['error'] = "Login information is not correct.";
		} else if($checkResult === -2) {
			$parameters['error'] = "Please try again later (you are locked out for too many failed attempts).";
		} else if($checkResult === 1) {
			$parameters['error'] = "You are not a root administrator.";
		}
	}
}

if(isset($_SESSION['root'])) {
	get_page_advanced("index", "root", $parameters);
} else {
	$parameters['user_loggedin'] = isset($_SESSION['user_id']);
	get_page_advanced("index_login", "root", $parameters);
}
?>
