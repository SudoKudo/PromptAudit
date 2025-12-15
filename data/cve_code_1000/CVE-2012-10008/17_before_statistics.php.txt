<?php
include("../config.php");
include("../include/common.php");
include("../include/db_connect.php");
include("../include/session.php");

include("../include/apply_gen.php");
include("../include/statistics.php");

if(isset($_SESSION['admin_id'])) {
	$club_id = escape(getAdminClub($_SESSION['admin_id']));
	
	$adminStat = adminStatistics($club_id);
	$responseStat = responseStatistics($club_id, true, 8);
	
	get_page_advanced("statistics", "admin", array('adminStat' => $adminStat, 'responseStat' => $responseStat));
} else {
	header('Location: index.php?error=' . urlencode("You are not logged in!"));
}
?>
