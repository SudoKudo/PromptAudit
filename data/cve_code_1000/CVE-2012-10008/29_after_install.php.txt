<?php
include("../include/common.php");
include("../config.php");
include("../include/db_connect.php");
include("../include/session.php");

//make sure that users aren't set up yet
$result = mysql_query("SELECT COUNT(*) FROM users");
$row = mysql_fetch_row($result);

if($row[0] == 0) {
	mysql_query("INSERT INTO users (username, password, name, email, register_time, accessed) VALUES ('admin', '" . chash("") . "', 'Site Administrator', 'admin@example.com', '0', '0')");
	$admin_id = escape(mysql_insert_id());
	mysql_query("INSERT INTO user_groups (user_id, `group`) VALUES ('$admin_id', '0')");
	mysql_query("INSERT INTO user_groups (user_id, `group`) VALUES ('$admin_id', '-1')");
}

?>
