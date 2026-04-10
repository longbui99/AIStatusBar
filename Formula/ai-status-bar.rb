class AiStatusBar < Formula
  desc "AI service usage in your macOS menu bar via SwiftBar"
  homepage "https://github.com/longbui99/AIStatusBar"
  url "https://github.com/longbui99/AIStatusBar.git", branch: "main"
  version "0.1.0"
  license "GPL-3.0-only"

  depends_on :macos
  depends_on "python@3"

  def install
    prefix.install Dir["*"]
    bin.install_symlink prefix/"bin/ai-status-bar"
  end

  def caveats
    <<~EOS
      Run the setup wizard to get started:
        ai-status-bar setup

      This will install SwiftBar (if needed) and let you choose providers.
    EOS
  end

  test do
    assert_match "ai-status-bar", shell_output("#{bin}/ai-status-bar help")
  end
end
