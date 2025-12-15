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
    $userBalance = mysql_result($userResult,0,"actualBalance");
    $userTeamId  = mysql_result($userResult,0,"teamId");

}


$query = "SELECT * from confirmedSquad WHERE teamId=$userTeamId;";
$result = mysql_query($query);
$string = '';
$playerList = array();

for($i=0;$i<mysql_num_rows($result);$i++)
{
    $playerList[] = mysql_result($result,$i,"playerId");
}
echo(implode(',',$playerList));

//for($i=0;$i<count($playerList);$i++)
//{
//    $playerQuery = "SELECT * FROM players where playerId= $playerList[$i];";
//    $playerResult = mysql_query($playerQuery);
//    $playerId = mysql_result($playerResult,0,"playerId");
//    $playerName    = mysql_result($playerResult,0,"name");
//    $playerCountry = mysql_result($playerResult,0,"country");
//    $playerType    = mysql_result($playerResult,0,"type");
//    $playerCaptain = mysql_result($playerResult,0,"captain");
//
//    $pcostquery = "SELECT * FROM playerData where playerId=$playerId";
//    $pcostresult = mysql_query($pcostquery);
//    $pcost = mysql_result($pcostresult,0,"cost");
//
//    echo('<div id="'.$playerId.'" class="userplayer row"><div class="col-sm-4">'.$playerName.'</div><div class="col-sm-3">'.$playerCountry.'</div><div class="col-sm-3">'.$playerType.'</div><div class="col-sm-1">'.$pcost.'</div><div class="col-sm-1">'.$playerCaptain."</div></div>");
//}

?>
