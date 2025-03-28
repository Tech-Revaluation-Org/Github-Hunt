import sys
import requests
import json
from datetime import datetime
import re
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                            QLabel, QLineEdit, QPushButton, QProgressBar, QTabWidget,
                            QTreeWidget, QTreeWidgetItem, QFileDialog)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QPalette, QColor

class GitHubWorker(QThread):
    progress = pyqtSignal(int)
    result = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            analyzer = GitHubAnalyzer(self.url)
            result = analyzer.analyze()
            self.progress.emit(100)
            self.result.emit(result)
        except Exception as e:
            self.error.emit(str(e))

class GitHubAnalyzer:
    def __init__(self, url):
        self.is_profile = self._is_profile_url(url)
        if self.is_profile:
            self.owner = self._parse_profile_url(url)
            self.repo = None
            self.base_url = None
            self.user_url = f"https://api.github.com/users/{self.owner}"
        else:
            self.owner, self.repo = self._parse_repo_url(url)
            self.base_url = f"https://api.github.com/repos/{self.owner}/{self.repo}"
            self.user_url = f"https://api.github.com/users/{self.owner}"
        self.headers = {"Accept": "application/vnd.github.v3+json"}

    def _is_profile_url(self, url):
        return bool(re.match(r"^https?://github\.com/[^/]+$", url))

    def _parse_profile_url(self, url):
        pattern = r"github\.com/([^/]+)"
        match = re.search(pattern, url)
        if not match:
            raise ValueError("Invalid GitHub profile URL")
        return match.group(1)

    def _parse_repo_url(self, url):
        pattern = r"github\.com/([^/]+)/([^/]+)"
        match = re.search(pattern, url)
        if not match:
            raise ValueError("Invalid GitHub repository URL")
        return match.group(1), match.group(2).replace('.git', '')

    def get_repo_details(self):
        if not self.repo:
            return {}
        try:
            response = requests.get(self.base_url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            languages_response = requests.get(f"{self.base_url}/languages", headers=self.headers)
            languages = languages_response.json() if languages_response.status_code == 200 else {}
            return {
                "id": data.get("id", "N/A"), "node_id": data.get("node_id", "N/A"),
                "full_name": data.get("full_name", "N/A"), "description": data.get("description", ""),
                "created_at": data.get("created_at", "N/A"), "updated_at": data.get("updated_at", "N/A"),
                "pushed_at": data.get("pushed_at", "N/A"), "stargazers_count": data.get("stargazers_count", 0),
                "watchers_count": data.get("watchers_count", 0), "forks_count": data.get("forks_count", 0),
                "open_issues_count": data.get("open_issues_count", 0), "primary_language": data.get("language", "N/A"),
                "all_languages": languages, "size": data.get("size", 0), "default_branch": data.get("default_branch", "N/A"),
                "has_issues": data.get("has_issues", False), "has_wiki": data.get("has_wiki", False),
                "has_pages": data.get("has_pages", False), "has_projects": data.get("has_projects", False),
                "has_downloads": data.get("has_downloads", False), "archived": data.get("archived", False),
                "disabled": data.get("disabled", False), "topics": data.get("topics", []),
                "homepage": data.get("homepage", ""), "fork": data.get("fork", False),
                "parent": data.get("parent", {}).get("full_name", None),
                "source": data.get("source", {}).get("full_name", None),
                "license": data.get("license", {}).get("name", None) if data.get("license") else None
            }
        except requests.exceptions.RequestException as e:
            print(f"Error fetching repo details: {e}")
            return {"error": str(e)}

    def get_owner_profile(self):
        try:
            response = requests.get(self.user_url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            events = requests.get(f"{self.user_url}/events/public", headers=self.headers).json() or []
            repos = requests.get(f"{self.user_url}/repos", headers=self.headers).json() or []
            followers = requests.get(f"{self.user_url}/followers", headers=self.headers).json() or []
            following = requests.get(f"{self.user_url}/following", headers=self.headers).json() or []

            activity = [{"type": e.get("type", "N/A"), "repo": e.get("repo", {}).get("name", "N/A"),
                        "created_at": e.get("created_at", "N/A"),
                        "payload": e.get("payload", {}).get("action", "N/A")} for e in events[:10]]
            repo_summary = {
                "total_public_repos": len(repos),
                "repo_names": [r.get("name", "N/A") for r in repos[:5]] if repos else [],
                "most_starred": max([r.get("stargazers_count", 0) for r in repos], default=0) if repos else 0,
                "total_forks": sum(r.get("forks_count", 0) for r in repos) if repos else 0
            }
            return {
                "user_id": data.get("id", "N/A"), "node_id": data.get("node_id", "N/A"),
                "login": data.get("login", "N/A"), "type": data.get("type", "N/A"),
                "avatar_url": data.get("avatar_url", ""), "html_url": data.get("html_url", ""),
                "created_at": data.get("created_at", "N/A"), "updated_at": data.get("updated_at", "N/A"),
                "public_repos": data.get("public_repos", 0), "public_gists": data.get("public_gists", 0),
                "followers": len(followers), "following": len(following),
                "follower_list": [f.get("login", "N/A") for f in followers[:5]] if followers else [],
                "following_list": [f.get("login", "N/A") for f in following[:5]] if following else [],
                "hireable": data.get("hireable", False), "blog": data.get("blog", ""),
                "location": data.get("location", ""), "email": data.get("email", ""),
                "bio": data.get("bio", ""), "twitter_username": data.get("twitter_username", ""),
                "company": data.get("company", ""), "public_activity": activity, "repo_summary": repo_summary
            }
        except requests.exceptions.RequestException as e:
            print(f"Error fetching owner profile: {e}")
            return {"error": str(e)}

    def get_collaborators(self):
        if not self.repo:
            return {}
        try:
            collabs_response = requests.get(f"{self.base_url}/collaborators", headers=self.headers)
            collabs = collabs_response.json() if collabs_response.status_code == 200 else []
            return {
                "total_collaborators": len(collabs),
                "collaborators": [{"login": c.get("login", "N/A"), "id": c.get("id", "N/A")}
                                for c in collabs[:5]] if collabs else []
            }
        except requests.exceptions.RequestException as e:
            print(f"Error fetching collaborators: {e}")
            return {"error": str(e)}

    def get_commit_activity(self):
        if not self.repo:
            return {}
        try:
            stats_response = requests.get(f"{self.base_url}/stats/commit_activity", headers=self.headers)
            stats = stats_response.json() if stats_response.status_code == 200 else []
            if not stats:
                return {"status": "processing"}
            total_commits = sum(week.get("total", 0) for week in stats)
            most_active = max(stats, key=lambda x: x.get("total", 0), default={"week": 0, "total": 0})
            return {
                "year_total_commits": total_commits,
                "most_active_week": {"timestamp": most_active.get("week", 0), "commits": most_active.get("total", 0)},
                "weekly_average": total_commits / len(stats) if stats else 0
            }
        except requests.exceptions.RequestException as e:
            print(f"Error fetching commit activity: {e}")
            return {"error": str(e)}

    def get_traffic(self):
        if not self.repo:
            return {}
        try:
            views_response = requests.get(f"{self.base_url}/traffic/views", headers=self.headers)
            clones_response = requests.get(f"{self.base_url}/traffic/clones", headers=self.headers)
            traffic = {}
            if views_response.status_code == 200:
                views = views_response.json()
                traffic["views"] = {"count": views.get("count", 0), "uniques": views.get("uniques", 0)}
            if clones_response.status_code == 200:
                clones = clones_response.json()
                traffic["clones"] = {"count": clones.get("count", 0), "uniques": clones.get("uniques", 0)}
            return traffic if traffic else {"note": "Traffic data not publicly available"}
        except requests.exceptions.RequestException as e:
            print(f"Error fetching traffic: {e}")
            return {"error": str(e)}

    def get_contributions(self):
        try:
            repos_response = requests.get(f"{self.user_url}/repos", headers=self.headers)
            repos = repos_response.json() if repos_response.status_code == 200 else []
            total_contribs = sum(r.get("stargazers_count", 0) + r.get("forks_count", 0) for r in repos)
            return {"total_contributions_impact": total_contribs}
        except requests.exceptions.RequestException as e:
            print(f"Error fetching contributions: {e}")
            return {"error": str(e)}

    def analyze(self):
        analysis = {"timestamp": datetime.now().isoformat()}
        if self.is_profile:
            analysis["profile"] = f"{self.owner}"
            analysis["url"] = f"https://github.com/{self.owner}"
        else:
            analysis["repository"] = f"{self.owner}/{self.repo}"
            analysis["url"] = f"https://github.com/{self.owner}/{self.repo}"

        analysis["owner_profile"] = self.get_owner_profile()
        if self.repo:
            analysis["repo_details"] = self.get_repo_details()
            analysis["collaborators"] = self.get_collaborators()
            analysis["commit_activity"] = self.get_commit_activity()
            analysis["traffic"] = self.get_traffic()
        analysis["contributions"] = self.get_contributions()
        return analysis

class GitHubAnalyzerUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GitHub Analyzer Pro")
        self.setGeometry(100, 100, 900, 700)
        self.current_data = None
        self.setup_ui()
        self.apply_styles()

    def setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        header = QLabel("GitHub Analyzer Pro")
        header.setFont(QFont("Arial", 26, QFont.Weight.Bold))
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        input_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Enter GitHub URL (e.g., https://github.com/username or https://github.com/owner/repo)")
        self.url_input.setFont(QFont("Arial", 12))
        self.analyze_button = QPushButton("Analyze")
        self.analyze_button.setFont(QFont("Arial", 12))
        self.analyze_button.clicked.connect(self.start_analysis)
        self.save_button = QPushButton("Save as JSON")
        self.save_button.setFont(QFont("Arial", 12))
        self.save_button.clicked.connect(self.save_data)
        self.save_button.setEnabled(False)
        input_layout.addWidget(self.url_input, 3)
        input_layout.addWidget(self.analyze_button, 1)
        input_layout.addWidget(self.save_button, 1)
        layout.addLayout(input_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.tabs = QTabWidget()
        self.repo_tree = QTreeWidget()
        self.profile_tree = QTreeWidget()
        self.repo_tree.setHeaderLabel("Repository Data")
        self.profile_tree.setHeaderLabel("Profile Data")
        self.tabs.addTab(self.repo_tree, "Repository")
        self.tabs.addTab(self.profile_tree, "Profile")
        layout.addWidget(self.tabs)

        self.status_label = QLabel("Ready")
        self.status_label.setFont(QFont("Arial", 10))
        layout.addWidget(self.status_label)

    def apply_styles(self):
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(28, 28, 28))
        palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Base, QColor(40, 40, 40))
        palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Button, QColor(70, 130, 180))
        palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Highlight, QColor(135, 206, 235))
        self.setPalette(palette)

        self.setStyleSheet("""
            QLineEdit {padding: 10px; border: 2px solid #555; border-radius: 8px; background-color: #333;}
            QPushButton {padding: 10px; border: none; border-radius: 8px; background-color: #4682b4;}
            QPushButton:hover {background-color: #87ceeb;}
            QTreeWidget {border: 1px solid #555; border-radius: 5px; padding: 10px; background-color: #333;}
            QProgressBar {border: 1px solid #555; border-radius: 5px; text-align: center; background-color: #333;}
            QProgressBar::chunk {background-color: #4682b4; border-radius: 3px;}
            QTabWidget::pane {border: 1px solid #555; background-color: #333;}
            QTabBar::tab {background: #444; padding: 8px; border-top-left-radius: 5px; border-top-right-radius: 5px;}
            QTabBar::tab:selected {background: #4682b4;}
        """)

    def populate_tree(self, tree, data):
        tree.clear()
        for key, value in data.items():
            parent = QTreeWidgetItem(tree, [str(key)])
            self._add_tree_items(parent, value)

    def _add_tree_items(self, parent, value):
        if isinstance(value, dict):
            for k, v in value.items():
                child = QTreeWidgetItem(parent, [str(k)])
                self._add_tree_items(child, v)
        elif isinstance(value, list):
            for i, v in enumerate(value):
                child = QTreeWidgetItem(parent, [f"[{i}]"])
                self._add_tree_items(child, v)
        else:
            QTreeWidgetItem(parent, [str(value)])

    def start_analysis(self):
        url = self.url_input.text().strip()
        if not url:
            self.status_label.setText("Error: Please enter a URL")
            return

        self.analyze_button.setEnabled(False)
        self.save_button.setEnabled(False)
        self.progress_bar.setValue(0)
        self.repo_tree.clear()
        self.profile_tree.clear()
        self.status_label.setText("Analyzing...")

        self.worker = GitHubWorker(url)
        self.worker.progress.connect(self.update_progress)
        self.worker.result.connect(self.display_results)
        self.worker.error.connect(self.show_error)
        self.worker.finished.connect(self.analysis_finished)
        self.worker.start()

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def display_results(self, result):
        self.current_data = result
        repo_data = {k: v for k, v in result.items() if k != "owner_profile"}
        profile_data = {"owner_profile": result["owner_profile"]}
        
        self.populate_tree(self.repo_tree, repo_data)
        self.populate_tree(self.profile_tree, profile_data)
        self.repo_tree.expandAll()
        self.profile_tree.expandAll()
        self.status_label.setText("Analysis completed")
        self.save_button.setEnabled(True)

    def show_error(self, error_message):
        self.repo_tree.clear()
        self.profile_tree.clear()
        error_item = QTreeWidgetItem(self.repo_tree, ["Error"])
        QTreeWidgetItem(error_item, [error_message])
        self.status_label.setText("Analysis failed")

    def analysis_finished(self):
        self.analyze_button.setEnabled(True)

    def save_data(self):
        if not self.current_data:
            self.status_label.setText("Error: No data to save")
            return
        file_name, _ = QFileDialog.getSaveFileName(self, "Save JSON", "", "JSON Files (*.json)")
        if file_name:
            try:
                with open(file_name, "w") as f:
                    json.dump(self.current_data, f, indent=2)
                self.status_label.setText(f"Saved to {file_name}")
            except Exception as e:
                self.status_label.setText(f"Error saving file: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GitHubAnalyzerUI()
    window.show()
    sys.exit(app.exec())
