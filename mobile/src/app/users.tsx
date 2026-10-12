// User management (admins): add people, set their role, reset passwords, turn accounts off.
import React, { useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { Button, Snackbar, TextInput } from 'react-native-paper';

import { Body, Card, Divider, Pill, Screen, Segmented, Sheet } from '@/components/ui';
import { usePalette, usePolling } from '@/hooks';
import { api } from '@/services/api';
import { useAppSelector } from '@/store';
import { fonts, timeAgo } from '@/theme';
import type { UserAccount } from '@/types';

type Role = UserAccount['role'];
const ROLE_HELP: Record<Role, string> = {
  admin: 'Everything, including users, privacy mode and robot setup',
  operator: 'Drive the robot, run inspections, talk to the assistant',
  viewer: 'Watch live data and read reports. Can press STOP',
};

export default function Users() {
  const p = usePalette();
  const me = useAppSelector((s) => s.session.username);
  const q = usePolling(() => api.users(), 30000, []);
  const [edit, setEdit] = useState<(Partial<UserAccount> & { password?: string; isNew?: boolean }) | null>(null);
  const [err, setErr] = useState('');
  const [snack, setSnack] = useState('');
  const [busy, setBusy] = useState(false);

  const save = async () => {
    if (!edit) return;
    setBusy(true);
    setErr('');
    try {
      if (edit.isNew) {
        await api.createUser({ username: edit.username!.trim(), password: edit.password!, role: edit.role!, name: edit.name?.trim() || undefined });
        setSnack(`${edit.username} added`);
      } else {
        await api.updateUser(edit.username!, { role: edit.role, name: edit.name, password: edit.password || undefined, disabled: edit.disabled });
        setSnack('Changes saved');
      }
      setEdit(null);
      q.refresh();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Screen onRefresh={q.refresh}>
        <Body soft style={{ marginTop: 8 }}>Each person signs in with their own account, so the activity log shows who did what.</Body>
        <Card style={{ paddingVertical: 2, marginTop: 14 }}>
          {(q.data ?? []).map((u, i) => (
            <View key={u.username}>
              {i ? <Divider /> : null}
              <View style={styles.row}>
                <View style={[styles.avatar, { backgroundColor: u.disabled ? p.sunken : p.primarySoft }]}>
                  <Text style={{ fontFamily: fonts.heading, color: u.disabled ? p.inkFaint : p.primary }}>{(u.name || u.username)[0].toUpperCase()}</Text>
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={{ fontFamily: fonts.bodyStrong, fontSize: 15, color: u.disabled ? p.inkFaint : p.ink }}>
                    {u.name || u.username}{u.username === me ? ' (you)' : ''}
                  </Text>
                  <Body small soft>{u.username}, last sign-in {timeAgo(u.last_login)}</Body>
                </View>
                {u.disabled ? <Pill small label="Off" /> : <Pill small level={u.role === 'admin' ? 'warn' : u.role === 'operator' ? 'ok' : 'idle'} label={u.role} />}
                <Button compact onPress={() => { setErr(''); setEdit({ ...u, password: '' }); }}>Edit</Button>
              </View>
            </View>
          ))}
        </Card>
        <Button mode="contained" icon="account-plus-outline" style={{ marginTop: 16 }} contentStyle={{ paddingVertical: 6 }}
          onPress={() => { setErr(''); setEdit({ isNew: true, username: '', name: '', password: '', role: 'operator' }); }}>
          Add user
        </Button>
      </Screen>

      <Sheet visible={!!edit} onDismiss={() => setEdit(null)} title={edit?.isNew ? 'Add user' : `Edit ${edit?.username}`}>
        {edit ? (
          <View style={{ gap: 12 }}>
            {edit.isNew ? (
              <TextInput mode="outlined" dense label="Username" autoCapitalize="none" value={edit.username}
                onChangeText={(username) => setEdit({ ...edit, username })} />
            ) : null}
            <TextInput mode="outlined" dense label="Full name" value={edit.name ?? ''} onChangeText={(name) => setEdit({ ...edit, name })} />
            <TextInput mode="outlined" dense secureTextEntry label={edit.isNew ? 'Password (6+ characters)' : 'New password (leave empty to keep)'}
              value={edit.password} onChangeText={(password) => setEdit({ ...edit, password })} />
            <Segmented value={edit.role as Role} onChange={(role) => setEdit({ ...edit, role })}
              options={[{ value: 'viewer', label: 'Viewer' }, { value: 'operator', label: 'Operator' }, { value: 'admin', label: 'Admin' }]} />
            <Body small soft>{ROLE_HELP[edit.role as Role]}</Body>
            {err ? <Body small style={{ color: p.danger }}>{err}</Body> : null}
            <View style={{ flexDirection: 'row', gap: 8 }}>
              {!edit.isNew && edit.username !== me ? (
                <>
                  <Button mode="outlined" onPress={() => setEdit({ ...edit, disabled: !edit.disabled })}>
                    {edit.disabled ? 'Turn on' : 'Turn off'}
                  </Button>
                  <Button mode="outlined" textColor={p.danger} onPress={async () => {
                    try { await api.deleteUser(edit.username!); setEdit(null); setSnack('User deleted'); q.refresh(); } catch (e: any) { setErr(e.message); }
                  }}>Delete</Button>
                </>
              ) : null}
              <Button mode="contained" style={{ flex: 1 }} loading={busy} onPress={save}
                disabled={busy || (edit.isNew && ((edit.username ?? '').trim().length < 2 || (edit.password ?? '').length < 6)) || (!!edit.password && edit.password.length < 6)}>
                {edit.isNew ? 'Add user' : 'Save'}
              </Button>
            </View>
          </View>
        ) : null}
      </Sheet>
      <Snackbar visible={!!snack} onDismiss={() => setSnack('')} duration={3000}>{snack}</Snackbar>
    </>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 10 },
  avatar: { width: 38, height: 38, borderRadius: 19, alignItems: 'center', justifyContent: 'center' },
});
