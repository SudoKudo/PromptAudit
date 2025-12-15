<?php
include("../config.php");
include("../include/common.php");
include("../include/db_connect.php");
include("../include/session.php");

include("../include/apply_gen.php");
include("../include/latex.php");

if(isset($_SESSION['admin_id'])) {
	$club_id = escape(getAdminClub($_SESSION['admin_id']));
	
	if(isset($_REQUEST['type'])) {
		if(isset($_REQUEST['done'])) {
			if($_REQUEST['name']!= "" && $_REQUEST['description']!=""){
				$type = trim($_REQUEST['type']);
				$name = trim($_REQUEST['name']);

			$description = str_replace("\r", "", trim($_REQUEST['description']));
			if($type == "select") $description = str_replace("\n", "; ", $description);

				$status = "optional";
				if(isset($_REQUEST['status'])) $status = trim($_REQUEST['status']);
			
				$showchars = "false";
				if(isset($_REQUEST['showchars'])) $showchars = trim($_REQUEST['showchars']);
			
				$length = 1000;
				if(isset($_REQUEST['length'])) $length = trim($_REQUEST['length']);
			
				$method = "";
				if(isset($_REQUEST['method'])) $method = trim($_REQUEST['method']);
			
			$size = "medium";
			if(isset($_REQUEST['size'])) $size = trim($_REQUEST['size']);

				$generate = $name . "\n";
				$generate .= $description . "\n";
				$type_line = "type:$type; status:$status";
				if($type=="essay" || $type=="short") {
					$type_line .= "; showchars:$showchars; length:$length; size:$size";
				} else if($type=="select") {
					   $type_line .= "; method:$method";
				}
				$generate .= $type_line;
				get_page_advanced("easyq_generated", "admin", array('generate' => $generate, 'name' => $name, 'description' => $description, 'type' => $type_line));
			} else {
				get_page_advanced("easyq_question", "admin", array('error' => "Question and Description are required", 'type' => $_REQUEST['type']));
			}
		} else {
			get_page_advanced("easyq_question", "admin", array('type' => $_REQUEST['type']));
		}
	} else {
		get_page_advanced("easyq_type", "admin");
	}
} else {
	header('Location: index.php?error=' . urlencode("You are not logged in!"));
}
?>
