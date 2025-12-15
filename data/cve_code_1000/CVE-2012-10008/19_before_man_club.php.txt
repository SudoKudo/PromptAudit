<?php
include("../config.php");
include("../include/common.php");
include("../include/db_connect.php");
include("../include/session.php");

if(isset($_SESSION['admin_id'])) {
	$club_id = escape(getAdminClub($_SESSION['admin_id']));
	$admin_id = escape($_SESSION['admin_id']);
	
	if($club_id != 0) {
		if(isset($_REQUEST['action'])){
			$currpass = mysql_query("SELECT password FROM admins WHERE id='" . $_SESSION['admin_id'] . "'");
			$currpass = mysql_fetch_array($currpass);
			if($_REQUEST['old_password']==$currpass[0]){
				if(isset($_REQUEST['description']) && isset($_REQUEST['view_time']) && isset($_REQUEST['open_time']) && isset($_REQUEST['close_time']) && isset($_REQUEST['user_type'])) {
					$description = escape($_REQUEST['description']);
					$view_time = strtotime($_REQUEST['view_time']);
					$open_time = strtotime($_REQUEST['open_time']);
					$close_time = strtotime($_REQUEST['close_time']);
					$num_recommend = escape($_REQUEST['num_recommend']);
					$user_type = escape($_REQUEST['user_type']);
					if($user_type == "Name"){
						$usernot = 1;
					} else {
						$usernot = 0;
					}
		
					mysql_query("UPDATE clubs SET description='$description', view_time='$view_time', open_time='$open_time', close_time='$close_time', num_recommend='$num_recommend' WHERE id='$club_id'");
					$success = "Account Updated!";
				}
				if(isset($_REQUEST['new_password'])) {
					$changepass = changeAdminPass($admin_id,$_REQUEST['new_password'],$_REQUEST['new_password_conf']);
					if($changepass == 1){
						$success = "Password Updated!";
					} else if($changepass == -2){
						$error = "New password does not match!";
					} else {
						$error = "Invaid new password!";
					}
				}
			} else {
				$error = "Incorrect password! If you have forgotten this password, contact your rood advisor.";
			}
		} else {
			$info = "You need your current password to make any changes!";
		}
		
		$result = mysql_query("SELECT c.name, a.email, c.description, c.view_time, c.open_time, c.close_time, c.num_recommend FROM clubs c, admins a WHERE c.id='$club_id' AND a.id='$admin_id'");
	
		if($row = mysql_fetch_array($result)) {
			if( isset($error) ) {
				get_page_advanced("man_club", "admin", array('error'=> $error, 'email' => $row['email'], 'club_name' => $row['name'], 'description' => $row['description'], 'view_time' => $row['view_time'], 'open_time' => $row['open_time'], 'close_time' => $row['close_time'], 'num_recommend' => $row['num_recommend']));
			} else if( isset($success) ){
				get_page_advanced("man_club", "admin", array('success' => $success, 'email' => $row['email'], 'club_name' => $row['name'], 'description' => $row['description'], 'view_time' => $row['view_time'], 'open_time' => $row['open_time'], 'close_time' => $row['close_time'], 'num_recommend' => $row['num_recommend']));
			} else if( isset($info) ){
				get_page_advanced("man_club", "admin", array('info' => $info, 'email' => $row['email'], 'club_name' => $row['name'], 'description' => $row['description'], 'view_time' => $row['view_time'], 'open_time' => $row['open_time'], 'close_time' => $row['close_time'], 'num_recommend' => $row['num_recommend']));
			} else if( isset($warning) ){
				get_page_advanced("man_club", "admin", array('warning' => $warning, 'email' => $row['email'], 'club_name' => $row['name'], 'description' => $row['description'], 'view_time' => $row['view_time'], 'open_time' => $row['open_time'], 'close_time' => $row['close_time'], 'num_recommend' => $row['num_recommend']));
			} else {
				get_page_advanced("man_club", "admin", array('email' => $row['email'], 'club_name' => $row['name'], 'description' => $row['description'], 'view_time' => $row['view_time'], 'open_time' => $row['open_time'], 'close_time' => $row['close_time'], 'num_recommend' => $row['num_recommend']));
			}
		} else {
			get_page_advanced("message", "admin", array('message' => "Error: your club cannot be found in the clubs table.", 'title' => "Manage Club"));
		}
	}
} else {
	header('Location: index.php?error=' . urlencode("You are not logged in!"));
}
