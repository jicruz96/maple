import { useTranslation } from "next-i18next"
import { useEffect, useMemo, useState } from "react"
import { useAuth } from "../auth"
import { Stack } from "../bootstrap"
import { firestore } from "../firebase"
import {
  collection,
  collectionGroup,
  getDocs,
  query,
  where,
  addDoc
} from "firebase/firestore"
import { FollowedItem, UserElement } from "./FollowingTabComponents"
import { UnfollowModalConfig } from "./UnfollowModal"

export const FollowersTab = ({ className }: { className?: string }) => {
  const { user } = useAuth()
  const uid = user?.uid

  // NEW: build a query over the collection group
  const followersQuery = useMemo(
    () =>
      uid
        ? query(
            collectionGroup(firestore, "activeTopicSubscriptions"),
            where("uid", "==", uid), // they follow *me*
            where("type", "==", "testimony") // user-to-user follows only
          )
        : null,
    [uid]
  )

  // query for people *I* follow so we can decide button state
  const myFollowsQuery = useMemo(
    () =>
      uid
        ? query(
            collection(firestore, `/users/${uid}/activeTopicSubscriptions/`),
            where("uid", "==", uid),
            where("type", "==", "testimony")
          )
        : null,
    [uid]
  )
  const [iFollowSet, setIFollowSet] = useState<Set<string>>(new Set())

  const [followers, setFollowers] = useState<UserElement[]>([])

  useEffect(() => {
    if (!followersQuery) return
    ;(async () => {
      const qs = await getDocs(followersQuery)
      const list: UserElement[] = []
      qs.forEach(doc => list.push(doc.data().userLookup)) // same field used elsewhere
      setFollowers(list)
    })()
  }, [followersQuery])

  useEffect(() => {
    if (!myFollowsQuery) return
    ;(async () => {
      const qs = await getDocs(myFollowsQuery)
      const ids = new Set<string>()
      qs.forEach(doc => ids.add(doc.data().userLookup.uid))
      setIFollowSet(ids)
    })()
  }, [myFollowsQuery])

  const [unfollow, setUnfollow] = useState<UnfollowModalConfig | null>(null)

  const { t } = useTranslation("editProfile")

  return (
    <Stack>
      <h2 className={className ? `pb-3 ${className}` : "pb-3"}>
        {t("follow.orgs")}
      </h2>
      {followers.map(element => (
        <FollowedItem
          key={element.profileId}
          element={element}
          alreadyFollowing={iFollowSet.has(element.profileId)}
          setFollow={async (targetUid: string) => {
            if (!uid || iFollowSet.has(targetUid)) return
            await addDoc(
              collection(firestore, `/users/${uid}/activeTopicSubscriptions/`),
              {
                uid,
                type: "testimony",
                userLookup: { uid: targetUid }
              }
            )
            setIFollowSet(new Set([...iFollowSet, targetUid]))
          }}
          setUnfollow={setUnfollow}
          type="org"
        />
      ))}
    </Stack>
  )
}
