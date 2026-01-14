
import requests
import subprocess
import os
import shutil
import tempfile
import getpass
from pathlib import Path
from typing import Optional

class FFmpegUpdater:
    def __init__(self, install_dir: Optional[str] = None):
        self.ffmpeg_url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz"
        
        # Get current username
        self.username = getpass.getuser()
        
        # Use provided install_dir or default to user's home directory
        if install_dir:
            self.install_dir = Path(install_dir)
        else:
            # Use Path.home() for cross-platform compatibility
            self.install_dir = Path.home() / 'ffmpeg'
        
        self.ffmpeg_binary = self.install_dir / 'bin' / 'ffmpeg'
        print(f"Running as user: {self.username}")
        print(f"Installation directory: {self.install_dir}")
        
    def get_version_date(self, version_str: str) -> Optional[str]:
        """Extract date from version string (e.g., N-118193-g5f38c82536-20241229 -> 20241229)"""
        try:
            parts = version_str.split('-')
            # Look for a part that looks like a date (8 digits)
            for part in reversed(parts):
                if part.isdigit() and len(part) == 8:
                    return part
            return None
        except Exception as e:
            print(f"Error parsing version date: {e}")
            return None
    
    def get_current_version(self) -> Optional[str]:
        """Get current FFmpeg version if installed"""
        if not self.ffmpeg_binary.exists():
            print(f"FFmpeg not found at {self.ffmpeg_binary}")
            return None
            
        try:
            result = subprocess.run(
                [str(self.ffmpeg_binary), '-version'], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                version_line = result.stdout.splitlines()[0]
                print(f"Current FFmpeg version: {version_line}")
                
                # Extract version string (usually after 'version')
                if 'version' in version_line:
                    version_part = version_line.split('version')[1].strip().split()[0]
                    return version_part
                return None
            else:
                print(f"Error checking FFmpeg version: {result.stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            print("Timeout checking FFmpeg version")
            return None
        except Exception as e:
            print(f"Error occurred while checking version: {e}")
            return None
    
    def download_ffmpeg(self, download_dir: Path) -> Optional[Path]:
        """Download latest FFmpeg to specified directory"""
        print('Downloading the latest FFmpeg version...')
        
        try:
            response = requests.get(self.ffmpeg_url, stream=True, timeout=60)
            response.raise_for_status()
            
            tar_file = download_dir / "ffmpeg-master-latest-linux64-gpl.tar.xz"
            
            # Get total size for progress tracking
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(tar_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            progress = (downloaded / total_size) * 100
                            print(f"\rDownload progress: {progress:.1f}%", end='', flush=True)
            
            print(f"\nDownloaded FFmpeg archive to {tar_file}")
            
            # Verify file is not corrupted (basic check)
            if tar_file.stat().st_size < 1024 * 1024:  # Less than 1MB is suspicious
                print("Warning: Downloaded file seems too small")
                return None
                
            return tar_file
            
        except requests.RequestException as e:
            print(f"\nFailed to download FFmpeg: {e}")
            return None
    
    def extract_ffmpeg(self, tar_file: Path, extract_dir: Path) -> Optional[Path]:
        """Extract FFmpeg tar.xz file"""
        try:
            print(f"Extracting {tar_file}...")
            result = subprocess.run(
                ['tar', '-xJf', str(tar_file), '-C', str(extract_dir)],
                check=True,
                capture_output=True,
                text=True
            )
            
            # Find the extracted directory
            extracted_dirs = [d for d in extract_dir.iterdir() if d.is_dir() and 'ffmpeg' in d.name.lower()]
            
            if not extracted_dirs:
                print("Could not find extracted FFmpeg directory")
                print(f"Contents of {extract_dir}: {list(extract_dir.iterdir())}")
                return None
                
            extracted_dir = extracted_dirs[0]
            print(f"Extracted FFmpeg to {extracted_dir}")
            return extracted_dir
            
        except subprocess.CalledProcessError as e:
            print(f"Error extracting FFmpeg: {e}")
            print(f"stderr: {e.stderr}")
            return None
        except Exception as e:
            print(f"Unexpected error during extraction: {e}")
            return None
    
    def get_extracted_version(self, extracted_dir: Path) -> Optional[str]:
        """Get version from extracted FFmpeg"""
        ffmpeg_bin = extracted_dir / 'bin' / 'ffmpeg'
        if not ffmpeg_bin.exists():
            print(f"FFmpeg binary not found in {ffmpeg_bin}")
            return None
            
        try:
            # Make binary executable
            ffmpeg_bin.chmod(0o755)
            
            result = subprocess.run(
                [str(ffmpeg_bin), '-version'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                version_line = result.stdout.splitlines()[0]
                print(f"Downloaded FFmpeg version: {version_line}")
                if 'version' in version_line:
                    version_part = version_line.split('version')[1].strip().split()[0]
                    return version_part
            return None
            
        except Exception as e:
            print(f"Error checking extracted version: {e}")
            return None
    
    def compare_versions(self, current_version: str, new_version: str) -> bool:
        """Compare two versions by date"""
        if not current_version or not new_version:
            return True  # Install if we can't compare
            
        current_date = self.get_version_date(current_version)
        new_date = self.get_version_date(new_version)
        
        if not current_date or not new_date:
            print("Could not extract dates from versions, proceeding with update")
            return True
            
        print(f"Current version date: {current_date}, New version date: {new_date}")
        
        if new_date == current_date:
            print("Versions are identical")
            return False
        
        return new_date > current_date
    
    def install_ffmpeg(self, source_dir: Path) -> bool:
        """Install FFmpeg from source directory"""
        try:
            # Verify source directory structure
            if not (source_dir / 'bin' / 'ffmpeg').exists():
                print(f"Invalid FFmpeg structure in {source_dir}")
                return False
            
            # Backup existing installation if it exists
            backup_dir = None
            if self.install_dir.exists():
                backup_dir = self.install_dir.with_name(self.install_dir.name + '.backup')
                if backup_dir.exists():
                    shutil.rmtree(backup_dir)
                print(f"Backing up existing installation to {backup_dir}")
                shutil.move(str(self.install_dir), str(backup_dir))
            
            # Create parent directory if needed
            self.install_dir.parent.mkdir(parents=True, exist_ok=True)
            
            # Move new installation
            shutil.move(str(source_dir), str(self.install_dir))
            
            # Make all binaries executable
            bin_dir = self.install_dir / 'bin'
            if bin_dir.exists():
                for binary in bin_dir.glob('*'):
                    if binary.is_file():
                        binary.chmod(0o755)
            
            print(f"FFmpeg successfully installed to {self.install_dir}")
            
            # Remove backup if installation successful
            if backup_dir and backup_dir.exists():
                shutil.rmtree(backup_dir)
                print("Removed backup")
                
            return True
            
        except Exception as e:
            print(f"Error installing FFmpeg: {e}")
            
            # Restore backup if available
            if backup_dir and backup_dir.exists():
                if self.install_dir.exists():
                    shutil.rmtree(self.install_dir)
                shutil.move(str(backup_dir), str(self.install_dir))
                print("Restored previous installation")
            
            return False
    
    def add_to_path_instructions(self):
        """Provide instructions for adding FFmpeg to PATH"""
        bin_path = self.install_dir / 'bin'
        
        print("\n" + "=" * 60)
        print("To use FFmpeg from anywhere, add it to your PATH:")
        print("=" * 60)
        
        # Detect shell
        shell = os.environ.get('SHELL', '/bin/bash')
        
        if 'bash' in shell:
            rc_file = Path.home() / '.bashrc'
        elif 'zsh' in shell:
            rc_file = Path.home() / '.zshrc'
        else:
            rc_file = Path.home() / '.profile'
        
        print(f"\nAdd this line to your {rc_file}:")
        print(f'export PATH="{bin_path}:$PATH"')
        print(f"\nOr run this command:")
        print(f'echo \'export PATH="{bin_path}:$PATH"\' >> {rc_file}')
        print(f"source {rc_file}")
        print("=" * 60)
    
    def update(self, force: bool = False) -> bool:
        """
        Main update method
        
        Args:
            force: Force update even if current version is up-to-date
        
        Returns:
            bool: True if successful, False otherwise
        """
        print("=" * 60)
        print("FFmpeg Updater")
        print("=" * 60)
        
        current_version = self.get_current_version()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Download latest version
            tar_file = self.download_ffmpeg(temp_path)
            if not tar_file:
                return False
            
            # Extract
            extracted_dir = self.extract_ffmpeg(tar_file, temp_path)
            if not extracted_dir:
                return False
            
            # Get new version
            new_version = self.get_extracted_version(extracted_dir)
            if not new_version:
                print("Could not determine downloaded version")
                return False
            
            # Compare versions
            if not force and current_version:
                if not self.compare_versions(current_version, new_version):
                    print(f"\nCurrent version ({current_version}) is already up-to-date!")
                    return True
            
            # Install new version
            action = 'Installing' if not current_version else 'Updating to'
            print(f"\n{action} FFmpeg version: {new_version}")
            success = self.install_ffmpeg(extracted_dir)
            
            if success:
                final_version = self.get_current_version()
                print("\n" + "=" * 60)
                print(f"✓ FFmpeg successfully {'installed' if not current_version else 'updated'}!")
                print(f"  User: {self.username}")
                print(f"  Version: {final_version}")
                print(f"  Location: {self.install_dir}")
                print("=" * 60)
                
                # Show PATH instructions if this is a new install
                if not current_version:
                    self.add_to_path_instructions()
            else:
                print("\n✗ Update failed!")
            
            return success


# Usage
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Update FFmpeg to the latest version')
    parser.add_argument('--install-dir', type=str, help='Custom installation directory')
    parser.add_argument('--force', action='store_true', help='Force update even if up-to-date')
    args = parser.parse_args()
    
    try:
        updater = FFmpegUpdater(install_dir=args.install_dir)
        success = updater.update(force=args.force)
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nUpdate cancelled by user")
        exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        exit(1)
