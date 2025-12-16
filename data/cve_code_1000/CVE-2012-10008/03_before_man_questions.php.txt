<?php
include("../config.php");
include("../include/common.php");
include("../include/db_connect.php");
include("../include/session.php");

include("../include/apply_gen.php");
include("../include/apply_admin.php");

if(isset($_SESSION['admin_id'])) {
	$club_id = escape(getAdminClub($_SESSION['admin_id']));
	include("category_manager.php");
	
	$message = "";
	$isAvailableWindow = false;
	$editInfo = 0;
	
	if($club_id != 0) {
		//output a warning if we are in the available window
		$isAvailableWindow = isAvailableWindow($club_id);
	}
	
	if(isset($_REQUEST['action'])) {
		if($_REQUEST['action'] == "edit" && isset($_REQUEST['id'])) {
			$qid = escape($_REQUEST['id']);
			
			//if the question is edited, update database
			// otherwise, show the edit form and hide add question forms
			if(isset($_REQUEST['varname']) && isset($_REQUEST['vardesc']) && isset($_REQUEST['vartype'])) {
				$varname = escape($_REQUEST['varname']);
				$vardesc = escape($_REQUEST['vardesc']);
				$vartype = escape($_REQUEST['vartype']);
				
				mysql_query("UPDATE $database SET varname='$varname', vardesc='$vardesc', vartype='$vartype' WHERE id='$qid' AND $whereString");
				$message = "Update successful!";
			} else {
				$result = mysql_query("SELECT varname, vardesc, vartype FROM $database WHERE id='$qid' AND $whereString");
				
				if($row = mysql_fetch_array($result)) {
					$editInfo = array($qid, $row['varname'], $row['vardesc'], $row['vartype']);
				}
			}
		} else if(($_REQUEST['action'] == "up" || $_REQUEST['action'] == "down") && isset($_REQUEST['id']) && isset($_REQUEST['orderId'])) {
			$qid = escape($_REQUEST['id']);
			$orderId = escape($_REQUEST['orderId']);
			
			$operation = "<"; //take next lower orderId if moving up, or next higher orderId if moving down
			$type = "MAX";
			if($_REQUEST['action'] == "down") {
				$operation = ">";
				$type = "MIN";
			}
			
			$result = mysql_query("SELECT $type(orderId) FROM $database WHERE $whereString AND orderId $operation '$orderId'");
			
			if($row = mysql_fetch_array($result)) {
				if(!is_null($row[0])) {
					$rowOrderId = escape($row[0]);
					mysql_query("UPDATE $database SET orderId='$orderId' WHERE orderId='$rowOrderId' AND $whereString");
					mysql_query("UPDATE $database SET orderId='$rowOrderId' WHERE id='$qid' AND $whereString");
					
					$message = "Move successful!";
				}
			}
		} else if($_REQUEST['action'] == "Add question") {
			if(isset($_REQUEST['varname']) && isset($_REQUEST['vardesc']) && isset($_REQUEST['vartype'])) {
				$result = insertQuestion($_REQUEST['varname'], $_REQUEST['vardesc'], $_REQUEST['vartype'], $club_id, $database, $whereString);
				
				if($result === TRUE) {
					$message = "Addition successful!";
				} else {
					$message = "Addition failed: $result";
				}
			}
		} else if($_REQUEST['action'] == "delete") {
			$qid = escape($_REQUEST['id']);
			mysql_query("DELETE FROM $database WHERE id='$qid'");
		} else if($_REQUEST['action'] == "Add multiple questions" && isset($_REQUEST['data'])) {
			$dataText = str_replace("\r", "", $_REQUEST['data']);
			$dataLines = explode("\n", $dataText);
			
			for($i = 0; $i < count($dataLines) - 2; $i+=3) {
				$result = insertQuestion($dataLines[$i], $dataLines[$i + 1], $dataLines[$i + 2], $club_id, $database, $whereString);
				
				if($result === TRUE) {
					$message = "Addition successful!";
				} else {
					$message = "Addition failed: $result";
				}
			}
		} else if($_REQUEST['action'] == "deleteall") {
			deleteQuestions($database, $whereString);
		}
	}
	
	$result = mysql_query("SELECT id, orderId, varname, vardesc, vartype FROM $database WHERE $whereString ORDER BY orderId");
	$questionList = array();
	
	while($row = mysql_fetch_array($result)) {
		array_push($questionList, array($row[0], $row[1], $row[2], $row[3], $row[4]));
	}
	
	get_page_advanced("man_questions", "admin", array("message" => $message, "editInfo" => $editInfo, "questionList" => $questionList, "categories" => $categories, "isAvailableWindow" => $isAvailableWindow));
} else {
	header('Location: index.php?error=' . urlencode("You are not logged in!"));
}
?>
