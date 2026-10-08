# Tuoni make argument completion. Requires Bash 4.2+ and bash-completion.
# Source this file, or install it with `make install-completion`.

if (( BASH_VERSINFO[0] < 4 || (BASH_VERSINFO[0] == 4 && BASH_VERSINFO[1] < 2) )); then
    printf '%s\n' 'Tuoni completion requires Bash 4.2+; on macOS use Zsh or Homebrew Bash.' >&2
    return 1
fi

# Homebrew uses /opt/homebrew on Apple Silicon and /usr/local on Intel Macs.
# Honor an explicit prefix or ask brew for custom installations.
_tuoni_completion_prefixes=(/usr /usr/local /opt/homebrew)
_tuoni_completion_brew_prefix=${HOMEBREW_PREFIX:-}
if [[ ! $_tuoni_completion_brew_prefix ]] && command -v brew >/dev/null 2>&1; then
    _tuoni_completion_brew_prefix=$(brew --prefix 2>/dev/null) || _tuoni_completion_brew_prefix=
fi
if [[ $_tuoni_completion_brew_prefix ]]; then
    _tuoni_completion_prefixes=("$_tuoni_completion_brew_prefix" "${_tuoni_completion_prefixes[@]}")
fi
unset _tuoni_completion_brew_prefix

if ! declare -F _get_comp_words_by_ref >/dev/null; then
    for _tuoni_completion_prefix in "${_tuoni_completion_prefixes[@]}"; do
        for _tuoni_completion_file in "$_tuoni_completion_prefix/share/bash-completion/bash_completion" "$_tuoni_completion_prefix/etc/profile.d/bash_completion.sh"; do
            if [[ -r $_tuoni_completion_file ]]; then
                source "$_tuoni_completion_file"
                break 2
            fi
        done
    done
    if ! declare -F _get_comp_words_by_ref >/dev/null && [[ -r /etc/bash_completion ]]; then
        source /etc/bash_completion
    fi
fi
if ! declare -F _get_comp_words_by_ref >/dev/null; then
    unset _tuoni_completion_prefixes _tuoni_completion_prefix _tuoni_completion_file
    printf '%s\n' 'Tuoni completion requires Bash 4.2+ and bash-completion (Homebrew: brew install bash bash-completion@2).' >&2
    return 1
fi

# Keep the existing Make completer for targets, flags, and other repositories.
_tuoni_make_spec=$(complete -p make 2>/dev/null) || _tuoni_make_spec=
if [[ $_tuoni_make_spec != *' -F _tuoni_make '* && $_tuoni_make_spec != *' -F _tuoni_make make' ]]; then
    if [[ ! $_tuoni_make_spec ]]; then
        for _tuoni_completion_prefix in "${_tuoni_completion_prefixes[@]}"; do
            _tuoni_completion_file=$_tuoni_completion_prefix/share/bash-completion/completions/make
            if [[ -r $_tuoni_completion_file ]]; then
                source "$_tuoni_completion_file"
                break
            fi
        done
        _tuoni_make_spec=$(complete -p make 2>/dev/null) || _tuoni_make_spec=
    fi
    if [[ $_tuoni_make_spec =~ -F[[:space:]]+([^[:space:]]+) ]]; then
        _tuoni_make_fallback=${BASH_REMATCH[1]}
    fi
fi
unset _tuoni_make_spec _tuoni_completion_prefixes _tuoni_completion_prefix _tuoni_completion_file

_tuoni_make()
{
    local cur prev words cword
    _get_comp_words_by_ref -n = cur prev words cword
    local make_dir=$PWD target= word directory i key value prefix partial choice choices selected
    local formats='shellcode-native dotnet-dll dotnet-exe native-lib' systems='windows linux'
    local selected_formats= selected_systems= REPLY
    local keys=(NAME FOLDER EXECUNITS OS PYTHON) used=() os_values=()
    COMPREPLY=()

    for ((i = 1; i < cword; i++)); do
        word=${words[i]}
        case "$word" in
            -C|--directory)
                ((i++))
                directory=${words[i]}
                ;;
            -C?*) directory=${word#-C} ;;
            --directory=*) directory=${word#*=} ;;
            -f|--file|--makefile)
                # A custom Makefile can have a different argument contract.
                target=
                break
                ;;
            --file=*|--makefile=*) target=; break ;;
            new-command|new-listener) target=$word; continue ;;
            EXECUNITS=*) selected_formats=${word#*=}; used+=(EXECUNITS); continue ;;
            OS=*) selected_systems=${word#*=}; used+=(OS); continue ;;
            *=*) used+=("${word%%=*}"); continue ;;
            *) continue ;;
        esac
        # bash-completion's dequoter rejects command substitutions.
        if declare -F _comp_dequote >/dev/null && _comp_dequote "$directory"; then
            directory=${REPLY[0]}
        else
            directory=${directory#\"}; directory=${directory%\"}
            directory=${directory#\'}; directory=${directory%\'}
        fi
        case "$directory" in
            /*) make_dir=$directory ;;
            *) make_dir=$make_dir/$directory ;;
        esac
    done

    if [[ ! $target || ! -f $make_dir/tools/scaffold_plugin.py || ! -f $make_dir/Makefile || $cur == -* || $prev == -C || $prev == --directory ]]; then
        if [[ ${_tuoni_make_fallback:-} ]] && declare -F "$_tuoni_make_fallback" >/dev/null; then
            "$_tuoni_make_fallback" "$@"
        fi
        return
    fi

    compopt +o default +o bashdefault 2>/dev/null || :
    if [[ $cur != *=* ]]; then
        for key in "${keys[@]}"; do
            [[ " ${used[*]} " == *" $key "* ]] && continue
            [[ $key= == "$cur"* ]] && COMPREPLY+=("$key=")
        done
        compopt -o nospace 2>/dev/null || :
        return
    fi

    key=${cur%%=*}
    value=${cur#*=}
    case "$key" in
        EXECUNITS|OS)
            # Both comma lists and quoted space lists are accepted by the CLI.
            value=${value#\"}; value=${value%\"}
            value=${value#\'}; value=${value%\'}
            prefix= partial=$value
            if [[ $value =~ ^(.*[[:space:],])([^[:space:],]*)$ ]]; then
                prefix=${BASH_REMATCH[1]}
                partial=${BASH_REMATCH[2]}
            fi
            selected=${prefix//,/ }
            selected=${selected,,}
            selected=${selected//_/-}
            selected_systems=${selected_systems//[\"\']/}
            selected_formats=${selected_formats//[\"\']/}
            selected_systems=${selected_systems,,}
            selected_formats=${selected_formats,,}
            selected_formats=${selected_formats//_/-}
            if [[ $key == EXECUNITS ]]; then
                read -r -a os_values <<< "${selected_systems//,/ }"
                [[ ${#os_values[@]} == 1 && ${os_values[0]} == linux ]] && formats=native-lib
                choices=$formats
            else
                if [[ $selected_formats && " ${selected_formats//,/ } " != *' native-lib '* ]]; then
                    systems=windows
                fi
                choices=$systems
            fi
            for choice in $choices; do
                [[ " $selected " == *" $choice "* ]] && continue
                [[ $choice == "$partial"* ]] && COMPREPLY+=("$prefix$choice")
            done
            compopt -o nospace 2>/dev/null || :
            ;;
        FOLDER)
            cur=$value
            while IFS= read -r -d '' directory; do
                [[ ! $directory ]] && continue
                [[ $directory != */ ]] && directory+=/
                COMPREPLY+=("$directory")
            done < <(cd -- "$make_dir" && _filedir -d && printf '%s\0' "${COMPREPLY[@]}")
            compopt -o filenames -o nospace 2>/dev/null || :
            ;;
        PYTHON)
            while IFS= read -r choice; do
                [[ " ${COMPREPLY[*]} " == *" $choice "* ]] || COMPREPLY+=("$choice")
            done < <(compgen -c -- "${value:-python}")
            ;;
        NAME) ;; # Names are free text, rather than a fixed list of choices.
    esac
    # Readline replaces only the portion after '=' when it is a word break.
    if [[ $COMP_WORDBREAKS != *=* ]]; then
        for ((i = 0; i < ${#COMPREPLY[@]}; i++)); do
            COMPREPLY[i]=$key=${COMPREPLY[i]}
        done
    fi
}

complete -o bashdefault -o default -F _tuoni_make make
