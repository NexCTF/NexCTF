# Bash completion for the `manager` CLI, as printed by `manager --show-completion bash`.
_manager_completion() {
    local IFS=$'\n'
    COMPREPLY=( $( env COMP_WORDS="${COMP_WORDS[*]}" \
                   COMP_CWORD=$COMP_CWORD \
                   _MANAGER_COMPLETE=complete_bash $1 ) )
    return 0
}

complete -o default -F _manager_completion manager
