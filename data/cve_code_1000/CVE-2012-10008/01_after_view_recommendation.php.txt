<?php
include("../config.php");
include("../include/common.php");
include("../include/db_connect.php");
include("../include/session.php");

if(isset($_SESSION['admin']) && isset($_REQUEST['peer_pdf']) && isset($_REQUEST['user_id'])) {
	//todo: admins can see any peer recommendations if they know the user ID
	$peer_pdf = escape($_REQUEST['peer_pdf']);
	$user_id = escape($_REQUEST['user_id']);
	$result = mysql_query("SELECT author, email FROM recommendations WHERE filename = '$peer_pdf' AND user_id = '$user_id'");
	
	if($row = mysql_fetch_array($result)) {
		get_page_advanced("view_recommendation", "admin", array('author' => $row[0], 'email' => $row[1], 'filename' => $peer_pdf));
	} else {
		get_page_advanced("message", "admin", array("title" => "Error", "message" => "Could not find requested recommendation!"));
	}
} else {
	header('Location: index.php');
}
?>
