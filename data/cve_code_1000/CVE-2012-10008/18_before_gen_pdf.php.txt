<?php
include("../config.php");
include("../include/common.php");
include("../include/db_connect.php");
include("../include/session.php");

include("../include/apply_gen.php");
include("../include/latex.php");

if(isset($_SESSION['admin_id'])) {
	$club_id = escape(getAdminClub($_SESSION['admin_id']));
	include("category_manager.php"); //sets database and whereString based on club/category
	
	$message = "";
	
	if(isset($_REQUEST['gen'])) {
		$result = mysql_query("SELECT varname, vardesc, vartype, '' FROM $database WHERE $whereString ORDER BY orderId");
		if($club_id != 0) {
			$whereString = "id = '" . $club_id . "'";
			
			$clubInfo = clubInfo($club_id); //array (club name, club description, open_time, close_time, num_recommendations)
			$sectionheader = "Supplement: " . $clubInfo[0];
		} else {
			$sectionheader = "General Application";
		}
		$createResult = generatePDFByResult($result, "../pdf/", $sectionheader);
	
		if(!$createResult[0]) {
			$error = "Error during PDF generation: " . $createResult[1];
		} else {
			$basePath = basePath();
			$style = getStyle();
			$stylePath = $basePath . "/astyle/$style";
			$message = "<a href=\"../pdf/" . $createResult[1] . ".pdf\"><img src=\"" . $stylePath . "/images/application_word.png\" width=\"64\"></a>";
			$success="PDF made!";
		}
	}
	if(isset($error)) {
		get_page_advanced("gen_pdf", "admin", array('error' => $error, 'message' => $message, 'categories' => $categories));
	} else if(isset($success)) {
		get_page_advanced("gen_pdf", "admin", array('success' => $success, 'message' => $message, 'categories' => $categories));
	} else {
		get_page_advanced("gen_pdf", "admin", array('message' => $message, 'categories' => $categories));
	}
} else {
	header('Location: index.php?error=' . urlencode("You are not logged in!"));
}
?>
