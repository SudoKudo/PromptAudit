<?php
include("../include/common.php");
include("../config.php");
include("../include/db_connect.php");
include("../include/session.php");

if(isset($_SESSION['admin_id']) || isset($_SESSION['id'] ) ) {
	session_unset();
	$warning = "You have been logged out! You may not log in as two different account types at once!";
	get_page_advanced("index_login", "root", array("warning" => $warning));
}

if(isset($_REQUEST['action'])) {
	if($_REQUEST['action'] == 'logout') {
		session_unset();
		get_page_advanced("index_login", "root", array('success' => "You have been logged out!"));
	}
} else if(isset($_REQUEST['password'])) {
	if(checkRoot($_REQUEST['password'])) {
		$_SESSION['root'] = true;
		get_page_advanced("index", "root", array('success' => "You are now logged in!"));
	} else {
		get_page_advanced("index_login", "root", array('error' => "Password is incorrect or you have been locked out."));
	}
} else if(isset($_SESSION['root'])) {
	get_page_advanced("index", "root");
} else {
	get_page_advanced("index_login", "root");
}
?>
