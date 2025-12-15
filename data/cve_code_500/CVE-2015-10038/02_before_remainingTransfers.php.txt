<?php
session_start();
require './../includes/dbconfig.php';
$user = $_SESSION['user'];
if(!isset($user))
{
    header('Location: ./../login.php');
}

// Getting User Balance and data.

$userQuery = "SELECT * FROM userData WHERE userId1='$user' or userId2='$user' ; ";
$userResult = mysql_query($userQuery);

if(isset($userResult))
{
    $userBalance = mysql_result($userResult,0,"money");
    $userTeamId  = mysql_result($userResult,0,"teamId");
    $transferNum = mysql_result($userResult,0,"transferNum");

}

//$oldSquadQuery = "SELECT * FROM confirmedSquad where teamId='".$userTeamId."';";
//$oldSquadResult = mysql_query($oldSquadQuery);
//$oldids = array();
//
//for($i=0;$i<mysql_num_rows($oldSquadResult);$i++)
//{
//    $oldids[] = mysql_result($oldSquadResult,$i,"playerId");
//}
//
//
//$newSquadQuery = "SELECT * FROM userSquad where teamId='".$userTeamId."';";
//$newSquadResult = mysql_query($newSquadQuery);
//$newids = array();
//
//for($i=0;$i<mysql_num_rows($newSquadResult);$i++)
//{
//    $newids[] = mysql_result($newSquadResult,$i,"playerId");
//}
//
//$numchanges = 0;
//for($i=0;$i<mysql_num_rows($newSquadResult);$i++)
//{
//    if(!in_array($newids[$i],$oldids))
//    {
//        $numchanges++;
//    }
//}

echo($transferNum);
//echo('<h5 class="col-md-6">Transfers Remaining: '.$transferNum.'</h5>');
//echo('<h5 class="col-md-6">Changes: '.$numchanges.'</h5>');
