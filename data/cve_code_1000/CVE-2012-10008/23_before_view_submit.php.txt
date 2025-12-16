<?php
include("../config.php");
include("../include/common.php");
include("../include/db_connect.php");
include("../include/session.php");

include("../include/apply_submit.php");

if(isset($_SESSION['admin_id'])) {
	$club_id = escape(getAdminClub($_SESSION['admin_id']));
	$admin_id = escape($_SESSION['admin_id']);
	
	if($club_id != 0) {
		//check if this admin is using textboxes and categories
		$result = mysql_query("SELECT box_enabled, cat_enabled, comment_enabled FROM admins WHERE id='" . escape($_SESSION['admin_id']) . "'");
		$row = mysql_fetch_array($result);
		$box_enabled = ($row['box_enabled'] == 1) ? true : false;
		$cat_enabled = ($row['cat_enabled'] == 1) ? true : false;
		$comment_enabled = ($row['comment_enabled'] == 1) ? true : false;
	
		//defaults
		$toolsMap = array();
		$catList = array();
		$catFilter = "";
		$boxFilter = "";
		
		//we will need to construct a map from the application database IDs to the box and category note values if enabled
		// we do this now so that we can check if an entry exists already for updating the notes table
		if($box_enabled || $cat_enabled || $comment_enabled) {
			$toolsResult = mysql_query("SELECT application_id, box, category, comments FROM club_notes WHERE admin_id = '$admin_id'");
	
			while($row = mysql_fetch_array($toolsResult)) {
				$toolsMap[$row['application_id']] = array($row['box'], $row['category'], $row['comments']);
			}
		}
	
		//check if notes table needs to be updated; use toolsMap to see if INSERT or UPDATE should be used
		if(($box_enabled || $cat_enabled || $comment_enabled) && isset($_REQUEST['id'])) {
			$application_id = escape($_REQUEST['id']);
		
			//verify that it belongs to this admin's club
			$result = mysql_query("SELECT club_id FROM applications WHERE id = '$application_id'");
		
			if($row = mysql_fetch_array($result)) { //application exists
				if($row[0] == $club_id) { //club is correct
					//if the tools map does not contain the ID, then we have to add it to database
					if(!isset($toolsMap[$application_id])) {
						$toolsMap[$application_id] = array('', '');
						mysql_query("INSERT INTO club_notes (application_id, admin_id) VALUES ('$application_id', '$admin_id')");
					}
				
					//now we check what needs to be updated
					// since we pre-retrieved toolsMap, we have to update it to reflect the changes
				
					$updateString = "";
		
					if($box_enabled && isset($_REQUEST['box'])) {
						$updateString .= "box = '" . escape($_REQUEST['box']) . "', ";
						$toolsMap[$application_id][0] = $_REQUEST['box'];
					}
		
					if($cat_enabled && isset($_REQUEST['category'])) {
						$updateString .= "category = '" . escape($_REQUEST['category']) . "', ";
						$toolsMap[$application_id][1] = $_REQUEST['category'];
					}
		
					if($comment_enabled && isset($_REQUEST['comments'])) {
						$updateString .= "comments = '" . escape($_REQUEST['comments']) . "', ";
						$toolsMap[$application_id][2] = $_REQUEST['comments'];
					}
			
					if(strlen($updateString) > 0) {
						$updateString = substr($updateString, 0, -2);
						mysql_query("UPDATE club_notes SET $updateString WHERE application_id='$application_id' AND admin_id='$admin_id'");
					}
				}
			}
		}
	
		//box filter manager
		if($box_enabled) {
			//filter might already be set, so retrieve it
			// todo: somehow merge this code with the catfilter code, because it's the same..
		
			if(isset($_REQUEST['boxFilter'])) {
				//store filter in session so that we can get it when user changes something
				// this way, we don't have to worry about setting it everywhere
				$boxFilter = $_REQUEST['boxFilter'];
				$_SESSION['boxFilter'] = $boxFilter;
			} else if(isset($_SESSION['boxFilter'])) {
				$boxFilter = $_SESSION['boxFilter'];
			}
		}
	
		//category filter manager
		if($cat_enabled) {
			//first, we retrieve a list of categories (this will be used in dropdown as well)
			$catResult = mysql_query("SELECT name FROM club_notes_categories WHERE admin_id = '$admin_id'");
	
			while($row = mysql_fetch_array($catResult)) {
				array_push($catList, $row[0]);
			}
	
			// filter might already be set, so retrieve it
		
			if(isset($_REQUEST['catFilter'])) {
				//store catfilter in session so that we can get it when user changes something
				// this way, we don't have to worry about setting it everywhere
				$catFilter = $_REQUEST['catFilter'];
				$_SESSION['catFilter'] = $catFilter;
			} else if(isset($_SESSION['catFilter'])) {
				$catFilter = $_SESSION['catFilter'];
			}
		}
	
		//list the applications, applying filters only when we loop (inefficient but okay)
		$array = listCompletedApplications($club_id);
	
		get_page_advanced("view_submit", "admin", array("box_enabled" => $box_enabled, "cat_enabled" => $cat_enabled, "comment_enabled" => $comment_enabled, "catList" => $catList, "catFilter" => $catFilter, "boxFilter" => $boxFilter, "toolsMap" => $toolsMap, "array" => $array));
	} else {
		get_page_advanced("message", "admin", array('message' => "General application admin does not have a club to manage.", 'title' => "View submissions"));
	}
} else {
	header('Location: index.php?error=' . urlencode("You are not logged in!"));
}
?>
