<?php
include("../config.php");
include("../include/common.php");
include("../include/db_connect.php");
include("../include/session.php");

//check for $_REQUEST['id'] here because this page should never be accessed without an id set
if(isset($_SESSION['admin_id']) && $_REQUEST['id']) {
	$club_id = escape(getAdminClub($_SESSION['admin_id']));
	$admin_id = escape($_SESSION['admin_id']);
	$app_id = escape($_REQUEST['id']);
	
	if($club_id != 0) {
		//retrieve and display comments (if not found in table, comments have not been set yet so default to blank)
		$current_comments = "";
		$result = mysql_query("SELECT comments FROM club_notes WHERE application_id='$app_id' AND admin_id='$admin_id'");
		if($row = mysql_fetch_array($result)) {
			$current_comments = $row[0];
		}
		
		get_page_advanced("comments", "admin", array('comments' => $current_comments, 'app_id' => $app_id));
	} else {
		get_page_advanced("index", "admin", array('warning' => "General application admin does not have comments!"));
	}
} else {
	header('Location: index.php?error=' . urlencode("You are not logged in!"));
}
?>
