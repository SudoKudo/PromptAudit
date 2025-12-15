<?php
namespace NeoX\Controller;
use NeoX\Model;
use NeoX\Entity;
use NeoX\Classes;

require_once __DIR__ . "/../panel.php";

class TPanelPages extends TPanel {

  // public $accessLevel = 'admin';

  public function index() {
    $this->template->addStyle("style/admin.css");
    $this->template->addStyle("style/admin.pages.css");
    $this->template->addStyle("style/train/linker.css");
    $this->template->addScripts(array("js/system/object.js"));
    $this->template->addJSModules(array(
      "NeoX.Modules.Pages.Controls" => "js/module/pages/controls.js"
    ));

    $this->template->load("index", "panel/pages");
    $this->template->pageTitle = "Manage Pages | Admin Panel";
    $this->template->page = "pages_panel";
    
    $page = isset($_GET['page'])?$_GET['page']:1;
    $categoryId = isset($_GET['categoryId'])?intval($_GET['categoryId']):-1;
    $status = isset($_GET['status'])?intval($_GET['status']):-1;
    
    $per_page = 15;
    $pagination = "";
    $pageData = array();
    
    $categoryData = $this->core->entity("category")->select();
    $categoryList = array();
    
    while($result = $categoryData->fetch_array()) {
      $categoryList[$result[Entity\TCategory::$tok_id]] = $result[Entity\TCategory::$tok_name]; 
    }
    
    $this->template->currentCategory = $categoryId;
    $this->template->currentStatus = $status;
    $this->template->categoryList = $categoryList;
    
    $linkerModel = $this->core->model("pages", "panel");
    $count_data = $linkerModel->countPages($categoryId, $status)->fetch_array();
    
    if($count_data['total'] > 0) {
      $pages = ceil($count_data['total'] / $per_page);
      $start = ($page - 1) * $per_page;
      
      $query = $linkerModel->getPages($start, $per_page, $categoryId, $status);
      
      if(!$query || $query->num_rows < 1) {
        $query = $linkerModel->getPages(0, $per_page, $categoryId, $status);
      }
      
      while($result = $query->fetch_array()) {
        $pageData[] = array(
          "Id" => $result[Entity\TPage::$tok_id],
          "Title" => $result[Entity\TPage::$tok_title]
        );
      }
      
      require_once APP_DIR . "classes/Pagination.php";
      $paginationObj = new Classes\Pagination($pages, $page);
      $pagination_array = $paginationObj->generate();
      
      $this->template->pagination = (array) $pagination_array;
      $this->template->currentPage1 = $count_data;
      $this->template->currentPage = $page;
      $pagination = $this->template->fetch("pagination", "panel/pages");
    }
    
    $this->template->pageList = $pageData;
    $this->template->pagination = $pagination;
    
    $this->template->hide_right_box = true;
    $this->template->render();
  }

  public function add() {
    $this->template->addStyle("style/admin.pages.css");
    
    $pageTitle = '';
    $pageBody = '';
    $categoryId = 0;
    
    if(isset($_POST['submit'])) {
      $pageTitle = $_POST['pageTitle'];
      $pageBody = $_POST['pageBody'];
      $categoryId = $_POST['categoryId'];
      
      if($_POST['pageTitle'] != "" && $_POST['pageBody'] != "" && intval($_POST['categoryId']) > -1) {
        $this->Delphi()->PageAdd($pageTitle, $pageBody, $categoryId);
        $this->template->redirect = "panel.php?type=pages";
      }
    }
    
    $categoryData = $this->core->entity("category")->select();
    $categoryList = array();
    while($result = $categoryData->fetch_array()) {
      $categoryList[$result[Entity\TCategory::$tok_id]] = $result[Entity\TCategory::$tok_name]; 
    }
    $this->template->categoryList = $categoryList;
    
    $this->template->pageData = array(
      'Title' => $pageTitle,
      'CategoryId' => $categoryId,
      'Body' => $pageBody
    );
    
    $this->template->load("add", "panel/pages");
    $this->template->pageTitle = "Add Page | Admin Panel";
    $this->template->page = "add_pages_panel";

    $this->template->hide_right_box = true;
    $this->template->render();
  }

  public function edit() {
    if(!isset($_GET['pageid'])) return;
    if(!isset($_GET['page'])) {
      $page = 1;
    } else {
      $page = intval($_GET['page']);
    }
    
    $pageId = intval($_GET['pageid']);
    $pageData = $this->core->entity("page")->select(array("id" => $pageId));
    if($pageData->num_rows == 0) {
      $this->template->redirect = "panel.php?type=pages&page=" . $page;
    } else {
      $categoryData = $this->core->entity("category")->select();
      $categoryList = array();
      while($result = $categoryData->fetch_array()) {
        $categoryList[$result[Entity\TCategory::$tok_id]] = $result[Entity\TCategory::$tok_name]; 
      }
      $this->template->categoryList = $categoryList;
      
      $pageData = $pageData->fetch_array();
      $pageTitle = $pageData[Entity\TPage::$tok_title];
      $pageBody = $pageData[Entity\TPage::$tok_body];
      $categoryId = $pageData[Entity\TPage::$tok_categoryid];
    
      $this->template->pageData = array(
        'Id' => $pageId,
        'Title' => $pageTitle,
        'Body' => $pageBody,
        'CategoryId' => $categoryId
      );
      
      $this->template->addStyle("style/admin.pages.css");
  
      $this->template->currentPage = $page;
      $this->template->load("edit", "panel/pages");
      $this->template->pageTitle = "Edit Page | Admin Panel";
      
      $this->template->page = "edit_pages_panel";
      
      if(isset($_POST['submit'])) {
        if($_POST['pageTitle'] == $pageTitle && $_POST['pageBody'] == $pageBody) {
          $this->core->entity("page")->update($pageId, array("categoryid" => intval($_POST['categoryId'])));
          $this->template->redirect = "panel.php?type=pages&page=" . $page;
        } else if($_POST['pageTitle'] != "" && $_POST['pageBody'] != "" && intval($_POST['categoryId']) > -1) {
          //edit request to delphi
          $this->Delphi()->PageEdit($pageId, $_POST['pageTitle'], $_POST['pageBody'], $_POST['categoryId']);
          $this->template->redirect = "panel.php?type=pages&page=" . $page;
        }
      }
    }

    $this->template->hide_right_box = true;
    $this->template->render();
  }
  
  public function delete() {
    if(!isset($_GET['pageid'])) return;
    if(!isset($_GET['page'])) {
      $page = 1;
    } else {
      $page = intval($_GET['page']);
    }
    
    $pageId = (int) $_GET['pageid'];
    
    //delete page
    $query = $this->core->entity("page")->deleteWithData($pageId);
    
    $this->template->redirect = "panel.php?type=pages&page=" . $page;
    $this->template->render();
  }
 

}
?>