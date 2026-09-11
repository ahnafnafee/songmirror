if not contains "$HOME/dev/songmirror/.tools" $PATH
    # Prepending path in case a system-installed binary needs to be overridden
    set -x PATH "$HOME/dev/songmirror/.tools" $PATH
end
