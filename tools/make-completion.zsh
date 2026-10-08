# Tuoni make argument completion. Native Zsh completion.
# Source this file, or install it with `make install-completion`.

if (( ! $+functions[compdef] )); then
    autoload -Uz compinit
    compinit -D || return
fi

# Keep the existing Make completer for targets, flags, and other repositories.
if [[ ${_comps[make]} != _tuoni_make_zsh ]]; then
    typeset -g _tuoni_make_zsh_fallback=${_comps[make]:-_make}
    if (( ! $+functions[$_tuoni_make_zsh_fallback] )); then
        autoload -Uz "$_tuoni_make_zsh_fallback"
    fi
fi

_tuoni_make_zsh() {
    local make_dir=$PWD target= word directory key partial list_prefix normalized choice
    local selected_formats= selected_systems= i prefix_length
    local -a keys used choices selected os_values format_values
    keys=(NAME FOLDER EXECUNITS OS PYTHON)

    for ((i = 2; i < CURRENT; i++)); do
        # Remove shell quoting without evaluating the user's assignments.
        word=${(Q)words[i]}
        case $word in
            -C|--directory) ((i++)); directory=${(Q)words[i]} ;;
            -C?*) directory=${word#-C} ;;
            --directory=*) directory=${word#*=} ;;
            -f|--file|--makefile|-f?*|--file=*|--makefile=*) target=; break ;;
            new-command|new-listener) target=$word; continue ;;
            EXECUNITS=*) selected_formats=${word#*=}; used+=(EXECUNITS); continue ;;
            OS=*) selected_systems=${word#*=}; used+=(OS); continue ;;
            NAME=*|FOLDER=*|PYTHON=*) used+=("${word%%=*}"); continue ;;
            *) continue ;;
        esac
        case $directory in
            /*) make_dir=$directory ;;
            *) make_dir=$make_dir/$directory ;;
        esac
    done

    if [[ -z $target || ! -f $make_dir/tools/scaffold_plugin.py || ! -f $make_dir/Makefile || $PREFIX == -* || ${words[CURRENT-1]} == (-C|--directory) ]]; then
        "$_tuoni_make_zsh_fallback" "$@"
        return
    fi

    if [[ $PREFIX != *=* ]]; then
        for key in $keys; do
            (( ${used[(Ie)$key]} )) || choices+=("$key=")
        done
        compadd -S '' -- $choices
        return
    fi

    key=${PREFIX%%=*}
    IPREFIX+=${PREFIX%%=*}=
    PREFIX=${PREFIX#*=}
    case $key in
        EXECUNITS|OS)
            # Complete the last value in comma lists or quoted space lists.
            partial=${PREFIX##*[[:space:],]}
            prefix_length=$((${#PREFIX} - ${#partial}))
            list_prefix=
            if (( prefix_length )); then
                list_prefix=${PREFIX[1,prefix_length]}
                IPREFIX+=$list_prefix
                PREFIX=$partial
            fi
            normalized=${(L)list_prefix}
            normalized=${normalized//_/-}
            normalized=${normalized//,/ }
            selected=(${=normalized})
            selected_formats=${(L)selected_formats}
            selected_formats=${selected_formats//_/-}
            selected_formats=${selected_formats//,/ }
            selected_systems=${(L)selected_systems}
            selected_systems=${selected_systems//,/ }
            os_values=(${=selected_systems})
            format_values=(${=selected_formats})
            if [[ $key == EXECUNITS ]]; then
                choices=(shellcode-native dotnet-dll dotnet-exe native-lib)
                if (( ${#os_values} == 1 )) && [[ $os_values[1] == linux ]]; then
                    choices=(native-lib)
                fi
            else
                choices=(windows linux)
                if [[ -n $selected_formats ]] && (( ! ${format_values[(Ie)native-lib]} )); then
                    choices=(windows)
                fi
            fi
            for choice in $choices; do
                (( ${selected[(Ie)$choice]} )) || compadd -S '' -- "$choice"
            done
            ;;
        FOLDER) _files -/ -W "$make_dir" ;;
        PYTHON) _command_names ;;
        NAME) _message 'plugin name (free text)' ;;
    esac
}

compdef _tuoni_make_zsh make
