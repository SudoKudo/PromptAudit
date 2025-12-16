<?php
include("include/common.php");
include("config.php");
include("include/db_connect.php");
include("include/session.php");

if(isset($_SESSION['user_id'])) {
	get_page("message", array("title" => "Logged In", "message" => "You are already logged in! Click <a href=\"application/\">here</a> to continue."));
} else if(isset($_REQUEST['username']) && isset($_REQUEST['password'])) {
	$result = checkLogin($_REQUEST['username'], $_REQUEST['password']);
	
	if($result >= 0) {
		$_SESSION['user_id'] = $result;
		get_page("login", array("title" => "Logged In", "message" => "You are now logged in. Click <a href=\"application/\">here</a> to continue.", "redirect" => "application/"));
	} else if($result == -2) {
		get_page("login", array("title" => "Error", "message" => "Error: please try again later (you are locked out for too many failed attempts). Click <a href=\"login.php\">here</a> to try again."));
	} else if($result == -3) {
		get_page("login", array("title" => "Error", "message" => "Error: login and registration are currently disabled. Click <a href=\"login.php\">here</a> to try again."));
	} else if($result == -1) {
		get_page("login", array("title" => "Error", "message" => "Error: login information is not correct. Click <a href=\"login.php\">here</a> to try again."));
	} else {
		get_page("login", array("title" => "Error", "message" => "Error: internal error! Click <a href=\"login.php\">here</a> to try again."));
	}
} else {
	get_page("login");
}

?>
