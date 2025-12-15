<?php
include("../config.php");
include("../include/common.php");
include("../include/db_connect.php");
include("../include/session.php");

if(isset($_REQUEST['error'])) {
	$error = $_REQUEST['error'];
}

if(isset($_REQUEST['username']) && isset($_REQUEST['password'])) {
	$checkResult = checkAdmin($_REQUEST['username'], $_REQUEST['password']);
	
	if($checkResult !== FALSE) {
		$_SESSION['admin_id'] = $checkResult;
	} else {
		$error = "Incorrect username/password. You may be locked from your account. ";
	}
} else if(isset($_REQUEST['action']) && isset($_SESSION['admin_id'])) {
	if($_REQUEST['action'] == 'logout') {
		$success = "You are now logged out.";
		session_unset();
	}
}

if(isset($_SESSION['admin_id'])) {
	get_page_advanced("index", "admin");
} else if(isset($error)) {
	get_page_advanced("index_login", "admin", array('error' => $error));
} else if(isset($success)) {
	get_page_advanced("index_login", "admin", array('success' => $success));
} else {
	get_page_advanced("index_login", "admin");
}
?>
