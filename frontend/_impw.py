import pathlib
import re

# ============ 导入侧密码字段（UserManagement + LoginEnhanced） ============
for f in ['src/views/system/UserManagement.vue', 'src/views/auth/LoginEnhanced.vue']:
    p = pathlib.Path(f)
    t = p.read_text(encoding='utf-8')

    if 'importPassword' in t or '导入密码' in t:
        print('skip (has password field):', f)
        continue

    # UserManagement：文件 input 后无法直接加字段（动态 input），改为 confirm 前的 prompt 密码可选输入
    if 'UserManagement' in f:
        old = re.search(
            r"(      const result = res\.data \|\| res\n"
            r"      if \(result\.success\) \{\n"
            r"        const p = result\.preview \|\| \{\}\n)",
            t,
        )
        assert old, 'um import anchor'
        inject = (
            old.group(1)
            + "        // Phase E：加密包需要密码；预览失败且标记加密时提示输入\n"
            + "        let importPassword = ''\n"
            + "        if (result.success === false && /加密/.test(result.message || '')) {\n"
            + "          try {\n"
            + "            const { value } = await ElMessageBox.prompt(\n"
            + "              '该权限包已加密，请输入导出时设置的密码：', '解密密码',\n"
            + "              { inputType: 'password', inputValidator: (v: string) => (v ? true : '密码不能为空') }\n"
            + "            )\n"
            + "            importPassword = value || ''\n"
            + "          } catch { return }\n"
            + "        }\n"
        )
        # 重试一次带密码的上传：把 fd 追加 password 再 post
        retry = (
            "        if (importPassword) {\n"
            "          const fd2 = new FormData()\n"
            "          fd2.append('file', file)\n"
            "          fd2.append('password', importPassword)\n"
            "          const res2 = await post('/permission-packages/import', fd2, {\n"
            "            headers: { 'Content-Type': 'multipart/form-data' },\n"
            "          })\n"
            "          Object.assign(result, res2.data || res2)\n"
            "          if (!result.success) { ElMessage.error(result.message || '导入失败'); return }\n"
            "        }\n"
        )
        insert_at = old.end(1)
        t = t[:insert_at] + '\n' + retry.strip('\n') + t[insert_at:]
        p.write_text(t, encoding='utf-8')
        print('patched (retry w/ password):', f)
        continue

    # LoginEnhanced：同样在预览失败含“加密”时 prompt 密码并重传
    old = re.search(
        r"(    const res: any = await post\('/permission-packages/import', formData\)\n"
        r"    const body: any = res \|\| \{\}\n)",
        t,
    )
    assert old, 'login import anchor'
    inject = (
        old.group(1)
        + "    // Phase E：加密包重试\n"
        + "    let _body = body\n"
        + "    if ((body.success === false || body.code !== 200) && /加密/.test(body.message || body.detail || '')) {\n"
        + "      try {\n"
        + "        const { value } = await ElMessageBox.prompt(\n"
        + "          '该权限包已加密，请输入导出时设置的密码：', '解密密码',\n"
        + "          { inputType: 'password', inputValidator: (v: string) => (v ? true : '密码不能为空') }\n"
        + "        )\n"
        + "        const fd2 = new FormData()\n"
        + "        fd2.append('file', permissionFile.value)\n"
        + "        fd2.append('password', value || '')\n"
        + "        const r2: any = await post('/permission-packages/import', fd2)\n"
        + "        _body = r2 || {}\n"
        + "      } catch { ElMessage.error('已取消导入'); return }\n"
        + "    }\n"
    )
    t = t[:old.start()] + inject + t[old.end():]
    # 后续 body 引用切换为 _body
    seg_start = old.end()
    t = t[:seg_start] + t[seg_start:].replace('const body: any = res || {}', '', 1)
    t = t.replace('if (success && savedFileName)', 'const success2 = _body.success === true || _body.code === 200\n    const savedFileName = _body.saved_file_name || _body.file_name || permissionFile.value?.name || \'\'\n    if (success2 && savedFileName)', 1)
    t = t.replace('_body.errors', '_body.errors')
    p.write_text(t, encoding='utf-8')
    print('patched:', f)
