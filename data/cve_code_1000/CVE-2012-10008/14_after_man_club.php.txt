<h1>Club management</h1>

<!-- This page uses datetimepicker, from http://www.rainforestnet.com/datetimepicker/datetimepicker.htm, which is free software released under the GNU GPL v3.0. OneApp is not affiliated with this software. -->

<p>Here, you can edit settings for your club. View time is the time at which your club will be available for addition into a user's supplement list. Open time is the time when the club supplement can be submitted. Close time is the submission deadline. The number of recommendations field is the required number of recommendations for your club; there is no upper limit on the number that can be submitted, except the maximum number of recommendations a user can request (set in the configuration file).</p>

<p>The calendar icon to the right of certain fields allows you to more easily edit dates. Javascript must be enabled to use this function. Dates can always be entered manually, using any of the <a href="http://www.php.net/manual/en/datetime.formats.compound.php">supported formats</a>.</p>

<SCRIPT LANGUAGE="JavaScript" SRC="<?= $stylePath ?>/datetimepicker/datetimepicker_css.js"></SCRIPT>

<form method="post" action="man_club.php">
<table><tr>
<td colspan="2"><p>Description</p></td><tr><td colspan="2"><textarea width="100%" rows="8" name="description"><?= $description ?></textarea></td></tr>
<tr><td><p>View time</p></td><td><p>MM/DD/YY (hh:mm:ss)<br><input type="text" id="view_time" name="view_time" value="<?= date('m/d/y H:i:s', $view_time) ?>" /><img src="<?= $stylePath ?>/datetimepicker/images/cal.gif" onclick="javascript:NewCssCal('view_time', 'MMddyyyy', 'arrow', true)" style="cursor:pointer"/></p></td></tr>
<tr><td><p>Open time</p></td><td><input type="text" id="open_time" name="open_time" value="<?= date('m/d/y H:i:s', $open_time) ?>" /><img src="<?= $stylePath ?>/datetimepicker/images/cal.gif" onclick="javascript:NewCssCal('open_time', 'MMddyyyy', 'arrow', true)" style="cursor:pointer"/></td></tr>
<tr><td><p>Close time</p></td><td><input type="text" id="close_time" name="close_time" value="<?= date('m/d/y H:i:s', $close_time) ?>" /><img src="<?= $stylePath ?>/datetimepicker/images/cal.gif" onclick="javascript:NewCssCal('close_time', 'MMddyyyy', 'arrow', true)" style="cursor:pointer"/></td></tr>
<tr><td><p>Number of recommenations</p></td><td><input type="text" name="num_recommend" value="<?= $num_recommend ?>" /></td></tr>
<tr><td colspan ="2" align="right"><input type="submit" value="Update" /></td></tr>
</table>
</form>
