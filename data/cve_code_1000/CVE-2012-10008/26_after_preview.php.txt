<?php
include("../config.php");
include("../include/common.php");
include("../include/db_connect.php");
include("../include/session.php");

include("../include/apply_gen.php");

if(isset($_SESSION['admin'])) {
	$club_id = $_SESSION['admin_club_id'];
	include("category_manager.php");
	
	$result = mysql_query("SELECT varname, vardesc, vartype FROM $database WHERE $whereString ORDER BY orderId");
	$questionList = array();

	while($row = mysql_fetch_array($result)) {
		array_push($questionList, array($row[0], $row[1], $row[2]));
	}

	//categories list comes from the category manager
	get_page_advanced("preview", "admin", array('questionList' => $questionList, 'categories' => $categories));
} else {
	header('Location: index.php?error=' . urlencode("You are not logged in!"));
}
?>
